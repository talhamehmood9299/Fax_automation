from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, TesseractCliOcrOptions,
)
from docling_core.types.doc import PictureItem


def convert_document(url):
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.ocr_options.lang = ["eng"]
    pipeline_options.ocr_options = TesseractCliOcrOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, device=AcceleratorDevice.AUTO
    )
    pipeline_options.ocr_options.tesseract_cmd = 'tesseract'
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    source = url
    conv_res = doc_converter.convert(source)

    output_dir = Path("scratch")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = conv_res.input.file.stem

    picture_counter = 0
    for element, _level in conv_res.document.iterate_items():
        if isinstance(element, PictureItem):
            picture_counter += 1
            element_image_filename = output_dir / f"{doc_filename}-picture-{picture_counter}.png"
            image = element.get_image(conv_res.document)
            if image is not None:
                with element_image_filename.open("wb") as fp:
                    image.save(fp, "PNG")
            else:
                print(f"Warning: Skipped a PictureItem—no image extracted for {element_image_filename}")

    return conv_res.document.export_to_markdown()

