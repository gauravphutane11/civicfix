from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None


@dataclass
class ImageAnalysisResult:
    brightness: float
    edge_density: float
    color_variance: float
    tags: list = field(default_factory=list)
    supporting_confidence: float = 0.0
    method: str = "civic_scene_relevance_gate"
    relevant: bool = True
    rejection_reason: str | None = None
    document_score: float = 0.0
    face_dominance: float = 0.0
    civic_relevance: float = 0.0


def _pixel_stats(path: Path):
    with Image.open(path) as original:
        original = ImageOps.exif_transpose(original).convert("RGB")
        width, height = original.size
        preview = original.copy()
        preview.thumbnail((700, 700))

        gray = preview.convert("L")
        sample = gray.resize((120, 120))

        brightness = ImageStat.Stat(gray).mean[0]
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_density = min(
            1.0,
            ImageStat.Stat(edges).mean[0] / 65.0,
        )

        rgb_stat = ImageStat.Stat(preview)
        color_variance = min(
            1.0,
            (sum(rgb_stat.stddev) / 3) / 85.0,
        )

        white_ratio = sum(
            1
            for value in sample.getdata()
            if value >= 242
        ) / (120 * 120)

        dark_ratio = sum(
            1
            for value in sample.getdata()
            if value <= 70
        ) / (120 * 120)

        return (
            width,
            height,
            brightness,
            edge_density,
            color_variance,
            white_ratio,
            dark_ratio,
            preview,
        )


def _opencv_signals(preview: Image.Image):
    if cv2 is None or np is None:
        return 0, 0.0, 0.0, 0.0

    array = np.asarray(preview)
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)

    faces = 0
    face_dominance = 0.0
    line_score = 0.0
    text_block_score = 0.0

    try:
        cascade = cv2.CascadeClassifier(
            str(
                Path(cv2.data.haarcascades)
                / "haarcascade_frontalface_default.xml"
            )
        )

        detected = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(36, 36),
        )

        faces = len(detected)

        if faces:
            image_area = float(
                gray.shape[0] * gray.shape[1]
            )
            largest = max(
                float(w * h)
                for (_, _, w, h) in detected
            )
            face_dominance = largest / image_area
    except Exception:
        pass

    try:
        threshold = cv2.Canny(
            gray,
            70,
            150,
        )

        lines = cv2.HoughLinesP(
            threshold,
            1,
            np.pi / 180,
            threshold=48,
            minLineLength=max(
                25,
                min(gray.shape) // 9,
            ),
            maxLineGap=8,
        )

        count = (
            0
            if lines is None
            else len(lines)
        )

        pixels = (
            gray.shape[0] * gray.shape[1]
        )

        line_score = min(
            1.0,
            count / max(
                36.0,
                pixels / 5200.0,
            ),
        )
    except Exception:
        pass

    # Screenshots/documents tend to produce repeated long horizontal/vertical
    # edges. A simple morphological projection gives us a second text/block cue.
    try:
        binary = cv2.threshold(
            gray,
            210,
            255,
            cv2.THRESH_BINARY_INV,
        )[1]

        horizontal = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (max(9, gray.shape[1] // 35), 1),
            ),
        )

        vertical = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (1, max(9, gray.shape[0] // 35)),
            ),
        )

        block_pixels = cv2.countNonZero(
            horizontal + vertical
        )
        total_pixels = float(
            gray.shape[0] * gray.shape[1]
        )
        text_block_score = min(
            1.0,
            (block_pixels / max(total_pixels, 1.0)) * 8.0,
        )
    except Exception:
        pass

    return (
        faces,
        face_dominance,
        line_score,
        text_block_score,
    )


def _category_score(
    category: str,
    brightness: float,
    edge_density: float,
    color_variance: float,
    dark_ratio: float,
    preview: Image.Image,
) -> float:
    """Broad scene cues used only as a relevance gate."""

    if category in {
        "pothole",
        "road_infrastructure",
    }:
        surface_texture = min(
            1.0,
            edge_density * 1.65,
        )
        rough_surface = min(
            1.0,
            dark_ratio * 1.45
            + color_variance * 0.75,
        )
        return 0.60 * surface_texture + 0.40 * rough_surface

    if category == "drainage":
        surface_scene = min(
            1.0,
            color_variance * 0.85
            + dark_ratio * 0.65
            + edge_density * 0.35,
        )
        return surface_scene

    if category == "garbage":
        clutter = min(
            1.0,
            edge_density * 1.35,
        )
        mixed_color = min(
            1.0,
            color_variance * 1.5,
        )
        return 0.55 * clutter + 0.45 * mixed_color

    if category == "streetlight":
        darkness = 1.0 - min(
            1.0,
            brightness / 255.0,
        )
        structure = min(
            1.0,
            edge_density * 1.4,
        )
        return 0.70 * darkness + 0.30 * structure

    if category == "water_supply":
        scene_variation = min(
            1.0,
            color_variance * 0.9
            + edge_density * 0.35,
        )
        return scene_variation

    return min(
        1.0,
        edge_density * 0.8
        + color_variance * 0.35,
    )


def _rejection(
    *,
    brightness: float,
    edge_density: float,
    color_variance: float,
    tags: list,
    reason: str,
    document_score: float,
    face_dominance: float,
    civic_relevance: float,
) -> ImageAnalysisResult:
    return ImageAnalysisResult(
        round(brightness, 1),
        round(edge_density, 3),
        round(color_variance, 3),
        tags,
        0.0,
        "civic_scene_relevance_gate",
        False,
        reason,
        round(document_score, 3),
        round(face_dominance, 3),
        round(civic_relevance, 3),
    )


def analyze_image(
    file_path: str,
    category: str,
) -> ImageAnalysisResult:
    path = Path(file_path)

    try:
        (
            width,
            height,
            brightness,
            edge_density,
            color_variance,
            white_ratio,
            dark_ratio,
            preview,
        ) = _pixel_stats(path)
    except Exception as exc:
        return _rejection(
            brightness=0,
            edge_density=0,
            color_variance=0,
            tags=[
                f"image_decode_failed: {exc.__class__.__name__}"
            ],
            reason=(
                "The uploaded file could not be read as a valid image."
            ),
            document_score=0,
            face_dominance=0,
            civic_relevance=0,
        )

    if width < 320 or height < 240:
        return _rejection(
            brightness=brightness,
            edge_density=edge_density,
            color_variance=color_variance,
            tags=["image_too_small"],
            reason=(
                "Please upload a clear photo with at least 320×240 pixels."
            ),
            document_score=0,
            face_dominance=0,
            civic_relevance=0,
        )

    (
        faces,
        face_dominance,
        line_score,
        text_block_score,
    ) = _opencv_signals(preview)

    document_score = min(
        1.0,
        0.42 * white_ratio
        + 0.22 * min(1.0, edge_density * 2.4)
        + 0.18 * line_score
        + 0.18 * text_block_score,
    )

    civic_relevance = _category_score(
        category,
        brightness,
        edge_density,
        color_variance,
        dark_ratio,
        preview,
    )

    tags: list[str] = []

    if faces:
        tags.append(
            f"{faces} face-like region(s) detected"
        )

    if document_score >= 0.50:
        tags.append(
            "Document/screenshot-like composition detected"
        )

    category_tag = {
        "pothole": "Road-surface cues checked",
        "road_infrastructure": "Infrastructure-scene cues checked",
        "drainage": "Drainage/surface cues checked",
        "garbage": "Waste/clutter cues checked",
        "streetlight": "Night/structural cues checked",
        "water_supply": "Water/supply-scene cues checked",
    }.get(category, "Civic-scene cues checked")

    tags.append(category_tag)

    # ---------------------------------------------------------
    # 1. PERSONAL PHOTO / PORTRAIT GATE
    # ---------------------------------------------------------
    if (
        face_dominance >= 0.075
        or (
            faces >= 1
            and face_dominance >= 0.035
            and civic_relevance < 0.48
        )
    ):
        return _rejection(
            brightness=brightness,
            edge_density=edge_density,
            color_variance=color_variance,
            tags=tags + [
                "dominant portrait-like face"
            ],
            reason=(
                "This looks like a personal or portrait photo. "
                "Upload a photo showing the civic problem itself."
            ),
            document_score=document_score,
            face_dominance=face_dominance,
            civic_relevance=civic_relevance,
        )

    # ---------------------------------------------------------
    # 2. DOCUMENT / SYLLABUS / DIAGRAM / SCREENSHOT GATE
    # ---------------------------------------------------------
    aspect_ratio = width / max(float(height), 1.0)

    screenshot_like = (
        width >= 1400
        and height >= 700
        and 1.55 <= aspect_ratio <= 2.05
        and white_ratio >= 0.30
        and line_score >= 0.75
    )

    obvious_document = (
        (
            document_score >= 0.55
            and white_ratio >= 0.55
        )
        or (
            white_ratio >= 0.67
            and line_score >= 0.18
        )
        or screenshot_like
    )

    if obvious_document:
        return _rejection(
            brightness=brightness,
            edge_density=edge_density,
            color_variance=color_variance,
            tags=tags + [
                "document_diagram_screenshot_gate"
            ],
            reason=(
                "This looks like a syllabus, document, diagram or screenshot. "
                "Upload a real photo of the civic problem."
            ),
            document_score=document_score,
            face_dominance=face_dominance,
            civic_relevance=civic_relevance,
        )

    # ---------------------------------------------------------
    # 3. LOW-EVIDENCE GATE
    # ---------------------------------------------------------
    if civic_relevance < 0.30:
        return _rejection(
            brightness=brightness,
            edge_density=edge_density,
            color_variance=color_variance,
            tags=tags + [
                "weak civic-scene relevance"
            ],
            reason=(
                "The photo does not provide enough visual evidence of the reported civic problem. "
                "Upload a clear photo of the issue itself."
            ),
            document_score=document_score,
            face_dominance=face_dominance,
            civic_relevance=civic_relevance,
        )

    confidence = min(
        0.96,
        max(
            0.24,
            0.52 * civic_relevance
            + 0.26 * min(1.0, edge_density * 1.45)
            + 0.22 * color_variance,
        ),
    )

    tags.append(
        "Civic photo relevance gate passed; visual analysis is supporting evidence only."
    )

    return ImageAnalysisResult(
        round(brightness, 1),
        round(edge_density, 3),
        round(color_variance, 3),
        tags,
        round(confidence, 3),
        "civic_scene_relevance_gate",
        True,
        None,
        round(document_score, 3),
        round(face_dominance, 3),
        round(civic_relevance, 3),
    )
