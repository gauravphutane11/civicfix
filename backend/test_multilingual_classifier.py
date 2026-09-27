"""Lightweight regression checks for CivicFix multilingual classification."""

from backend.ai.classifier import classifier


CASES = [
    ("आमच्या रस्त्यावर खूप मोठा खड्डा आहे", "mr", "pothole"),
    ("कचरा अनेक दिवसांपासून उचललेला नाही", "mr", "garbage"),
    ("रस्त्यावरील पथदिवा बंद आहे", "mr", "streetlight"),
    ("नाला तुंबला आहे आणि पाणी साचले आहे", "mr", "drainage"),
    ("आमच्या भागात पाणी येत नाही", "mr", "water_supply"),
    ("रस्त्याचा डिव्हायडर तुटला आहे", "mr", "road_infrastructure"),
    ("સડક પર મોટો ખાડો છે", "gu", "pothole"),
    ("சாலையில் பெரிய பள்ளம் உள்ளது", "ta", "pothole"),
    ("రోడ్డుపై పెద్ద గుంత ఉంది", "te", "pothole"),
    ("রাস্তায় বড় গর্ত হয়েছে", "bn", "pothole"),
]


def main() -> None:
    for text, language, expected in CASES:
        result = classifier.classify(text, language_hint=language)
        assert result.language_code == language, (text, result.language_code)
        assert result.category == expected, (text, result.category, expected, result.all_scores)
        assert result.confidence >= 0.70, (text, result.confidence)
    print(f"multilingual regression: {len(CASES)}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
