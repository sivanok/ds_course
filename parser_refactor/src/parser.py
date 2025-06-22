import io
import base64
from collections import defaultdict
from typing import Tuple, Dict, Any, List
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc import TableItem, PictureItem, TextItem

from .models import PDFObject, DocumentModel, ObjectType
from .utils import parse_location_tokens
from .logger import setup_logger
from .assistant_agents import ImageDescriptionAgent, DataFrameDescriptionAgent
from .settings import load_settings
from .gcs_manager import GCSManager

settings = load_settings(env_dev=True)


class DoclingToStructuredExtractor:
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.image_description_agent = ImageDescriptionAgent()
        self.dataframe_description_agent = DataFrameDescriptionAgent()
        self.gcs_manager = GCSManager()

    def load_docling_document(
        self, docling_filename: str
    ) -> Tuple[DoclingDocument, str]:
        bucket_name = settings.INPUT_BUCKET_NAME
        try:
            json_content = self.gcs_manager.download_text(bucket_name, docling_filename)
        except Exception as exc:
            self.logger.error(
                f"Unable to download docling file {docling_filename}: {exc}"
            )
            raise

        document = DoclingDocument.model_validate_json(json_content)
        base_name = docling_filename.replace("_docling.json", "")
        self.logger.debug(f"טעינת DoclingDocument הושלמה עבור: {docling_filename}")
        return document, base_name

    def _extract_location(self, item, document) -> int:
        try:
            location_str = item.get_location_tokens(document)
            return parse_location_tokens(location_str)
        except Exception as e:
            self.logger.warning(
                f"Failed to parse location tokens (inserts 1 instead): {e}"
            )
            return 1

    def parse_structured_data(
        self, docling_filename: str
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        self.logger.info(
            f"Starting to extract structured information from a file: {docling_filename}"
        )
        document, base_name = self.load_docling_document(docling_filename)

        structured_data: List[PDFObject] = []
        images_json: Dict[str, str] = {}
        image_counters = defaultdict(int)

        for item, _ in document.iterate_items(with_groups=False):
            prov_list = getattr(item, "prov", [])
            page_num = (
                prov_list[0].page_no
                if prov_list and hasattr(prov_list[0], "page_no")
                else None
            )

            location = self._extract_location(item, document)

            if isinstance(item, TextItem):
                label = getattr(item, "label", None)
                label_val = label.value if label else None
                obj_type = (
                    label_val
                    if label_val in {t.value for t in ObjectType}
                    else ObjectType.Text
                )
                object_id = f"{base_name}_page{page_num}_{obj_type.value}_{location}"
                pdf_obj = PDFObject(
                    object_id=object_id,
                    type=obj_type,
                    page=page_num,
                    location=location,
                    content=item.text,
                )

            elif isinstance(item, TableItem):
                object_id = f"{base_name}_page{page_num}_Table_{location}"
                try:
                    df = item.export_to_dataframe()
                    df.columns = df.columns.map(str)
                    description = self.dataframe_description_agent.run(df)
                    content = description
                except Exception as e:
                    self.logger.error(f"Error processing table: {e}")
                    content = "שגיאה בעיבוד טבלה"

                pdf_obj = PDFObject(
                    object_id=object_id,
                    type=ObjectType.Table,
                    page=page_num,
                    location=location,
                    content=content,
                )

            elif isinstance(item, PictureItem):
                object_id = f"{base_name}_page{page_num}_Image_{location}"
                try:
                    img = item.get_image(document)
                    if img:
                        buf_img = io.BytesIO()
                        img.save(buf_img, format="PNG")
                        b64_str = base64.b64encode(buf_img.getvalue()).decode("utf-8")
                        images_json[object_id] = b64_str
                        description = self.image_description_agent.run(b64_str)
                        content = description if description else "תיאור לא זמין"
                    else:
                        images_json[object_id] = None
                        content = "תמונה לא זמינה"
                except Exception as e:
                    self.logger.error(f"Error processing image: {e}")
                    images_json[object_id] = None
                    content = "שגיאה בעיבוד התמונה"

                pdf_obj = PDFObject(
                    object_id=object_id,
                    type=ObjectType.Image,
                    page=page_num,
                    location=location,
                    content=content,
                )
            else:
                continue

            try:
                structured_data.append(pdf_obj)
            except Exception as exc:
                self.logger.error(f"Failed to append object {object_id}: {exc}")

        main_json = DocumentModel(document=structured_data).dict()
        self.logger.info(f"Completed extract information for file: {base_name}")
        return main_json, images_json
