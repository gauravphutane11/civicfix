from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat

@dataclass
class ImageAnalysisResult:
    brightness: float
    edge_density: float
    color_variance: float
    tags: list = field(default_factory=list)
    supporting_confidence: float = 0.0
    method: str = "heuristic_pixel_analysis"

def _analyze_pixels(path: Path):
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((320, 320))
        gray = im.convert("L")
        brightness = ImageStat.Stat(gray).mean[0]
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_density = min(1.0, ImageStat.Stat(edges).mean[0] / 80.0)
        rgb_stat = ImageStat.Stat(im)
        color_variance = min(1.0, (sum(rgb_stat.stddev) / 3) / 90.0)
    return brightness, edge_density, color_variance

def analyze_image(file_path: str, category: str) -> ImageAnalysisResult:
    brightness, edge_density, color_variance = _analyze_pixels(Path(file_path))
    tags, confidence_signals = [], []
    if category == "pothole":
        if edge_density > 0.45:
            tags.append("High edge density detected -- consistent with a fractured road surface")
            confidence_signals.append(edge_density)
        else:
            tags.append("Edge density is moderate -- surface damage not strongly visible")
            confidence_signals.append(edge_density * 0.5)
    elif category == "garbage":
        if color_variance > 0.4:
            tags.append("High colour variance -- consistent with scattered mixed waste")
            confidence_signals.append(color_variance)
        else:
            tags.append("Low colour variance -- scene looks relatively uniform")
            confidence_signals.append(color_variance * 0.5)
    elif category == "streetlight":
        if brightness < 60:
            tags.append("Low overall brightness -- consistent with an unlit area at night")
            confidence_signals.append(1 - brightness / 255)
        else:
            tags.append("Image is well-lit -- cannot confirm a lighting outage from this photo alone")
            confidence_signals.append(0.2)
    elif category == "drainage":
        if edge_density < 0.3 and brightness > 90:
            tags.append("Smooth, reflective surface region detected -- consistent with standing water")
            confidence_signals.append(1 - edge_density)
        else:
            tags.append("No strong reflective/standing-water signal detected")
            confidence_signals.append(0.25)
    else:
        tags.append("General structural irregularity signal from edge analysis")
        confidence_signals.append(edge_density)
    tags.append("Heuristic pixel analysis only -- not a trained visual object detector; treat as supporting signal, not proof")
    confidence = min(0.95, max(0.05, sum(confidence_signals) / max(1, len(confidence_signals))))
    return ImageAnalysisResult(round(brightness, 1), round(edge_density, 3), round(color_variance, 3), tags, round(confidence, 3))
