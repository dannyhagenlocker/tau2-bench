#!/usr/bin/env python3
"""
Extract content from PowerPoint files for LaTeX conversion.

Usage:
    python extract_pptx.py presentation.pptx

Output:
    - presentation_content.md   : Structured markdown for reference
    - presentation_beamer.tex   : LaTeX Beamer file ready to customize
    - images/                   : Extracted images
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def get_slide_image_mapping(pptx_path):
    """Extract which images are used on each slide."""
    slide_images = {}

    with zipfile.ZipFile(pptx_path, "r") as z:
        rels_files = [
            f
            for f in z.namelist()
            if re.match(r"ppt/slides/_rels/slide\d+\.xml\.rels", f)
        ]

        for rels_file in rels_files:
            slide_num = int(re.search(r"slide(\d+)", rels_file).group(1))
            slide_images[slide_num] = []

            with z.open(rels_file) as f:
                content = f.read().decode("utf-8")
                image_refs = re.findall(
                    r'Target="\.\./(media/image\d+\.(png|jpg|jpeg|gif))"',
                    content,
                    re.IGNORECASE,
                )
                for img_ref, _ in image_refs:
                    img_name = img_ref.replace("../", "").replace("media/", "")
                    slide_images[slide_num].append(img_name)

    return slide_images


def extract_shapes_with_structure(xml_content):
    """Extract shapes with their text content, identifying titles and body text."""
    root = ET.fromstring(xml_content)
    shapes = []

    for sp in root.iter(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sp"
    ):
        shape_info = {"type": "body", "paragraphs": []}

        nvSpPr = sp.find(
            ".//{http://schemas.openxmlformats.org/presentationml/2006/main}nvSpPr"
        )
        if nvSpPr is not None:
            ph = nvSpPr.find(
                ".//{http://schemas.openxmlformats.org/presentationml/2006/main}ph"
            )
            if ph is not None:
                ph_type = ph.get("type", "")
                if "title" in ph_type.lower() or "ctrTitle" in ph_type:
                    shape_info["type"] = "title"
                elif "subTitle" in ph_type:
                    shape_info["type"] = "subtitle"

        txBody = sp.find(
            ".//{http://schemas.openxmlformats.org/presentationml/2006/main}txBody"
        )
        if txBody is None:
            txBody = sp.find(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/main}txBody"
            )

        if txBody is not None:
            for p_elem in txBody.iter(
                "{http://schemas.openxmlformats.org/drawingml/2006/main}p"
            ):
                para_text = []
                pPr = p_elem.find(
                    "{http://schemas.openxmlformats.org/drawingml/2006/main}pPr"
                )
                level = 0
                if pPr is not None:
                    level = int(pPr.get("lvl", 0))

                for t_elem in p_elem.iter(
                    "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                ):
                    if t_elem.text:
                        para_text.append(t_elem.text)

                if para_text:
                    shape_info["paragraphs"].append(
                        {"text": "".join(para_text), "level": level}
                    )

        if shape_info["paragraphs"]:
            shapes.append(shape_info)

    return shapes


def extract_notes(xml_content):
    """Extract speaker notes from notes XML."""
    root = ET.fromstring(xml_content)
    paragraphs = []

    for p_elem in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}p"):
        para_text = []
        for t_elem in p_elem.iter(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
        ):
            if t_elem.text:
                para_text.append(t_elem.text)
        if para_text:
            paragraphs.append("".join(para_text))

    notes = [p for p in paragraphs if p and not p.isdigit() and len(p) > 2]
    return notes


def extract_slide_content(pptx_path):
    """Extract all content from a PPTX file."""
    slides_data = []
    slide_images = get_slide_image_mapping(pptx_path)

    with zipfile.ZipFile(pptx_path, "r") as z:
        slide_files = sorted(
            [f for f in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml", f)],
            key=lambda x: int(re.search(r"slide(\d+)", x).group(1)),
        )

        for slide_file in slide_files:
            slide_num = int(re.search(r"slide(\d+)", slide_file).group(1))
            slide_data = {
                "number": slide_num,
                "title": "",
                "subtitle": "",
                "content": [],
                "notes": [],
                "images": slide_images.get(slide_num, []),
            }

            with z.open(slide_file) as f:
                xml_content = f.read()
                shapes = extract_shapes_with_structure(xml_content)

                for shape in shapes:
                    if shape["type"] == "title" and shape["paragraphs"]:
                        slide_data["title"] = shape["paragraphs"][0]["text"]
                    elif shape["type"] == "subtitle" and shape["paragraphs"]:
                        slide_data["subtitle"] = shape["paragraphs"][0]["text"]
                    else:
                        for para in shape["paragraphs"]:
                            slide_data["content"].append(para)

            notes_file = f"ppt/notesSlides/notesSlide{slide_num}.xml"
            if notes_file in z.namelist():
                with z.open(notes_file) as f:
                    notes_content = f.read()
                    slide_data["notes"] = extract_notes(notes_content)

            slides_data.append(slide_data)

    return slides_data


def extract_images(pptx_path, output_dir):
    """Extract all images from the PPTX."""
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(pptx_path, "r") as z:
        media_files = [f for f in z.namelist() if f.startswith("ppt/media/")]

        for media_file in media_files:
            filename = Path(media_file).name
            with z.open(media_file) as src:
                with open(images_dir / filename, "wb") as dst:
                    dst.write(src.read())

    return len(media_files)


def escape_latex(text):
    """Escape special LaTeX characters."""
    if not text:
        return ""

    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
        ("→", r"$\rightarrow$"),
        ("τ", r"$\tau$"),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    return text


def format_markdown(slides_data):
    """Format as Markdown for reference."""
    output = ["# Presentation Content\n"]

    for slide in slides_data:
        output.append(f"## Slide {slide['number']}")

        if slide["title"]:
            output.append(f"**{slide['title']}**\n")

        if slide["images"]:
            output.append(f"*Images: {', '.join(slide['images'])}*\n")

        if slide["content"]:
            for item in slide["content"]:
                indent = "  " * item["level"]
                output.append(f"{indent}- {item['text']}")
            output.append("")

        if slide["notes"]:
            output.append("**Notes:**")
            for note in slide["notes"]:
                if note.strip():
                    output.append(f"> {note}")
            output.append("")

        output.append("---\n")

    return "\n".join(output)


def format_latex(slides_data, title="Presentation"):
    """Format as LaTeX Beamer."""
    output = [
        f"""\\documentclass[aspectratio=169]{{beamer}}
\\usetheme{{Sierra}}

\\usepackage{{graphicx}}
\\graphicspath{{{{images/}}}}

\\title{{{escape_latex(title)}}}
\\author{{Your Name}}
\\institute{{Sierra AI}}
\\date{{\\today}}

\\begin{{document}}

\\begin{{frame}}
  \\titlepage
\\end{{frame}}
"""
    ]

    for slide in slides_data:
        output.append(f"% ===== SLIDE {slide['number']} =====")

        if slide["images"]:
            output.append(f"% Images: {', '.join(slide['images'])}")

        output.append("\\begin{frame}")

        if slide["title"]:
            output.append(f"  \\frametitle{{{escape_latex(slide['title'])}}}")

        if slide["images"]:
            output.append("  % Uncomment to add image:")
            output.append(
                f"  % \\includegraphics[width=0.8\\textwidth]{{{slide['images'][0].split('.')[0]}}}"
            )

        if slide["content"]:
            if len(slide["content"]) > 1:
                output.append("  \\begin{itemize}")
                for item in slide["content"]:
                    output.append(f"    \\item {escape_latex(item['text'])}")
                output.append("  \\end{itemize}")
            else:
                output.append(f"  {escape_latex(slide['content'][0]['text'])}")

        output.append("\\end{frame}\n")

        if slide["notes"]:
            output.append("% Speaker notes:")
            for note in slide["notes"]:
                output.append(f"% {note[:80]}...")
            output.append("")

    output.append("\\end{document}")
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Extract PowerPoint content for LaTeX conversion"
    )
    parser.add_argument("pptx_file", help="Path to the PowerPoint file")
    parser.add_argument("-o", "--output", help="Output directory", default=".")

    args = parser.parse_args()

    pptx_path = Path(args.pptx_file)
    output_dir = Path(args.output)

    if not pptx_path.exists():
        print(f"Error: File not found: {pptx_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting from: {pptx_path}")

    # Extract content
    slides_data = extract_slide_content(pptx_path)
    print(f"Found {len(slides_data)} slides")

    # Extract images
    num_images = extract_images(pptx_path, output_dir)
    print(f"Extracted {num_images} images")

    # Generate outputs
    base_name = pptx_path.stem

    md_path = output_dir / f"{base_name}_content.md"
    with open(md_path, "w") as f:
        f.write(format_markdown(slides_data))
    print(f"Markdown: {md_path}")

    tex_path = output_dir / f"{base_name}_slides.tex"
    with open(tex_path, "w") as f:
        f.write(format_latex(slides_data, title=base_name.replace("_", " ").title()))
    print(f"LaTeX: {tex_path}")

    print("\nDone! Edit the .tex file and compile with: xelatex " + tex_path.name)


if __name__ == "__main__":
    main()
