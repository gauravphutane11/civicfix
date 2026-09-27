"""Offline multilingual language detection and civic vocabulary normalization.

CivicFix intentionally keeps this layer local and deterministic. It does not send a
citizen's complaint to a third-party translation service. The classifier uses the
original wording plus a compact multilingual civic lexicon to create a normalized
English representation for the downstream ML models.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "or": "Odia",
    "pa": "Punjabi",
    "ur": "Urdu",
    "ne": "Nepali",
}

# Category vocabulary. Entries are deliberately short civic terms rather than
# full translations so that speech-to-text wording can vary naturally.
CATEGORY_LEXICON = {
    "pothole": {
        "en": ["pothole", "potholes", "crater", "road pit", "road hole"],
        "hi": ["गड्ढा", "गड्ढे", "सड़क में गड्ढा", "सड़क का गड्ढा", "gaddha", "gadde", "sadak par gaddha"],
        "mr": ["खड्डा", "खड्डे", "रस्त्यात खड्डा", "रस्त्यावरील खड्डा", "khadda", "khadde", "rastyavar khadda", "rastyavar motha khadda"],
        "gu": ["ખાડો", "ખાડા", "રસ્તામાં ખાડો", "રસ્તાનો ખાડો"],
        "bn": ["গর্ত", "গর্তগুলি", "রাস্তার গর্ত"],
        "ta": ["பள்ளம்", "சாலை பள்ளம்", "சாலையில் பள்ளம்"],
        "te": ["గుంత", "రోడ్డు గుంత", "రోడ్డులో గుంత"],
        "kn": ["ಗುಂಡಿ", "ರಸ್ತೆ ಗುಂಡಿ", "ರಸ್ತೆಯ ಗುಂಡಿ"],
        "ml": ["കുഴി", "റോഡിലെ കുഴി", "റോഡിൽ കുഴി"],
        "or": ["ଗାତ", "ରାସ୍ତାରେ ଗାତ", "ରାସ୍ତାର ଗାତ"],
        "pa": ["ਖੱਡਾ", "ਸੜਕ ਦਾ ਖੱਡਾ", "ਸੜਕ ਵਿਚ ਖੱਡਾ"],
        "ur": ["گڑھا", "سڑک کا گڑھا", "سڑک میں گڑھا"],
        "ne": ["खाल्डो", "सडकको खाल्डो"],
    },
    "garbage": {
        "en": ["garbage", "trash", "waste", "rubbish", "litter", "dumping", "dustbin", "bin"],
        "hi": ["कचरा", "कूड़ा", "कूड़ादान", "कूड़े का ढेर", "कचरा नहीं उठा", "kachra", "kooda", "kachra nahi utha"],
        "mr": ["कचरा", "कचराकुंडी", "कचऱ्याचा ढिग", "कचरा उचलला नाही", "कचरा साचला", "kachra", "kachryacha dhig", "kachra uchalla nahi"],
        "gu": ["કચરો", "કચરાપેટી", "કચરાનો ઢગલો", "કચરો ઉઠાવ્યો નથી"],
        "bn": ["আবর্জনা", "বর্জ্য", "কচরা", "ডাস্টবিন", "আবর্জনার স্তূপ"],
        "ta": ["குப்பை", "கழிவு", "குப்பைத்தொட்டி", "குப்பைகள்"],
        "te": ["చెత్త", "వ్యర్థాలు", "చెత్తబుట్ట", "చెత్త కుప్ప"],
        "kn": ["ಕಸ", "ತ್ಯಾಜ್ಯ", "ಕಸದ ಬುಟ್ಟಿ", "ಕಸದ ರಾಶಿ"],
        "ml": ["മാലിന്യം", "ചവറ്", "കുപ്പത്തൊട്ടി", "മാലിന്യക്കൂമ്പാരം"],
        "or": ["ଆବର୍ଜନା", "ବର୍ଜ୍ୟ", "କଚରା", "ଡଷ୍ଟବିନ"],
        "pa": ["ਕੂੜਾ", "ਗੰਦਗੀ", "ਕੂੜੇਦਾਨ", "ਕੂੜੇ ਦਾ ਢੇਰ"],
        "ur": ["کچرا", "کوڑا", "کوڑے دان", "کچرے کا ڈھیر"],
        "ne": ["फोहोर", "फोहर", "फोहोरको थुप्रो", "डस्टबिन"],
    },
    "streetlight": {
        "en": ["streetlight", "street light", "lamp post", "lamp", "lighting", "light is off"],
        "hi": ["स्ट्रीट लाइट", "सड़क की लाइट", "बत्ती", "लाइट बंद", "खंभे की लाइट", "street light band", "sadak ki light", "batti band"],
        "mr": ["पथदिवा", "रस्त्यावरील दिवा", "स्ट्रीट लाईट", "दिवा बंद", "रस्त्याचा दिवा", "pathdiva", "street light band", "rastyacha diva"],
        "gu": ["સ્ટ્રીટ લાઇટ", "રસ્તાની લાઇટ", "દીવો બંધ", "લાઇટ બંધ"],
        "bn": ["রাস্তার আলো", "স্ট্রিট লাইট", "বাতি বন্ধ", "ল্যাম্পপোস্ট"],
        "ta": ["தெருவிளக்கு", "சாலை விளக்கு", "விளக்கு அணைந்த", "ஸ்ட்ரீட் லைட்"],
        "te": ["వీధి దీపం", "రోడ్డు లైట్", "లైట్ పనిచేయడం లేదు", "స్ట్రీట్ లైట్"],
        "kn": ["ಬೀದಿ ದೀಪ", "ರಸ್ತೆ ದೀಪ", "ಲೈಟ್ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", "ಸ್ಟ್ರೀಟ್ ಲೈಟ್"],
        "ml": ["തെരുവ് വിളക്ക്", "റോഡ് ലൈറ്റ്", "വിളക്ക് കത്തുന്നില്ല", "സ്ട്രീറ്റ് ലൈറ്റ്"],
        "or": ["ରାସ୍ତା ଆଲୋକ", "ଷ୍ଟ୍ରିଟ ଲାଇଟ", "ଆଲୋକ ବନ୍ଦ", "ଲାମ୍ପପୋଷ୍ଟ"],
        "pa": ["ਸਟ੍ਰੀਟ ਲਾਈਟ", "ਸੜਕ ਦੀ ਬੱਤੀ", "ਬੱਤੀ ਬੰਦ", "ਲੈਂਪ ਪੋਸਟ"],
        "ur": ["اسٹریٹ لائٹ", "سڑک کی روشنی", "بتی بند", "لیمپ پوسٹ"],
        "ne": ["सडक बत्ती", "स्ट्रीट लाइट", "बत्ती निभेको"],
    },
    "drainage": {
        "en": ["drain", "drainage", "sewage", "sewer", "gutter", "culvert", "waterlogging", "blocked drain"],
        "hi": ["नाला", "नाली", "जल निकासी", "सीवेज", "गटर", "नाली बंद", "जलभराव", "nala", "nali", "gutter", "paani bhara", "nali band"],
        "mr": ["नाला", "गटार", "ड्रेनेज", "सांडपाणी", "नाली", "नाला तुंबला", "पाणी साचले", "nala", "gutter", "drainage", "pani sachle", "nala tumbla"],
        "gu": ["નાળો", "ગટર", "ડ્રેનેજ", "ગંદુ પાણી", "નાળું બંધ", "પાણી ભરાવ"],
        "bn": ["নালা", "নিকাশি", "ড্রেন", "পয়ঃনিষ্কাশন", "নর্দমা", "জল জমে", "নালা বন্ধ"],
        "ta": ["சாக்கடை", "வடிகால்", "கழிவுநீர்", "கால்வாய்", "நீர் தேக்கம்", "வடிகால் அடைப்பு"],
        "te": ["కాలువ", "డ్రైనేజ్", "మురుగునీరు", "కాలువ మూసుకుపోయింది", "నీరు నిలిచిపోయింది"],
        "kn": ["ಚರಂಡಿ", "ಒಳಚರಂಡಿ", "ಚರಂಡಿ ಮುಚ್ಚಿದೆ", "ಕೊಳಚೆ ನೀರು", "ನೀರು ನಿಂತಿದೆ"],
        "ml": ["തോട്", "ഓട", "ഡ്രെയിനേജ്", "മലിനജലം", "ഓട അടഞ്ഞു", "വെള്ളക്കെട്ട്"],
        "or": ["ନାଳା", "ଡ୍ରେନ", "ନିଷ୍କାଶନ", "ପାଣି ଜମିଛି", "ନାଳା ବନ୍ଦ"],
        "pa": ["ਨਾਲਾ", "ਨਿਕਾਸੀ", "ਸੀਵਰੇਜ", "ਗਟਰ", "ਨਾਲੀ ਬੰਦ", "ਪਾਣੀ ਖੜ੍ਹਾ"],
        "ur": ["نالہ", "نالی", "نکاسی", "سیوریج", "گٹر", "نالہ بند", "پانی کھڑا"],
        "ne": ["नाला", "ढल निकास", "ढल", "ढल बन्द", "पानी जमेको"],
    },
    "road_infrastructure": {
        "en": ["divider", "footpath", "sidewalk", "railing", "guard rail", "bus shelter", "speed breaker", "road sign", "zebra crossing", "traffic signal"],
        "hi": ["डिवाइडर", "फुटपाथ", "पैदल मार्ग", "रेलिंग", "गार्ड रेल", "बस शेल्टर", "स्पीड ब्रेकर", "सड़क संकेत", "जेब्रा क्रॉसिंग", "ट्रैफिक सिग्नल", "divider", "footpath", "railing", "speed breaker", "traffic signal"],
        "mr": ["डिव्हायडर", "फुटपाथ", "पादचारी मार्ग", "रेलिंग", "गार्ड रेल", "बस थांबा", "स्पीड ब्रेकर", "रस्त्याचे चिन्ह", "झेब्रा क्रॉसिंग", "ट्रॅफिक सिग्नल", "divider", "footpath", "railing", "speed breaker", "traffic signal"],
        "gu": ["ડિવાઇડર", "ફૂટપાથ", "રેલિંગ", "ગાર્ડ રેલ", "બસ સ્ટોપ", "સ્પીડ બ્રેકર", "રોડ સાઇન", "ઝેબ્રા ક્રોસિંગ", "ટ્રાફિક સિગ્નલ"],
        "bn": ["ডিভাইডার", "ফুটপাত", "রেলিং", "গার্ডরেল", "বাস শেল্টার", "স্পিড ব্রেকার", "রাস্তার সাইন", "জেব্রা ক্রসিং", "ট্রাফিক সিগন্যাল"],
        "ta": ["நடைபாதை", "சாலை பிரிப்பான்", "தடுப்புச்சுவர்", "ரெயிலிங்", "பேருந்து நிறுத்தம்", "வேகத்தடை", "சாலை குறியீடு", "ஜீப்ரா கிராசிங்", "சிக்னல்"],
        "te": ["ఫుట్‌పాత్", "రోడ్డు డివైడర్", "రైలింగ్", "గార్డ్ రైల్", "బస్ షెల్టర్", "స్పీడ్ బ్రేకర్", "రోడ్డు గుర్తు", "జీబ్రా క్రాసింగ్", "ట్రాఫిక్ సిగ్నల్"],
        "kn": ["ಪಾದಚಾರಿ ಮಾರ್ಗ", "ರಸ್ತೆ ಡಿವೈಡರ್", "ರೇಲಿಂಗ್", "ಗಾರ್ಡ್ ರೈಲು", "ಬಸ್ ನಿಲ್ದಾಣ", "ಸ್ಪೀಡ್ ಬ್ರೇಕರ್", "ರಸ್ತೆ ಫಲಕ", "ಜೀಬ್ರಾ ಕ್ರಾಸಿಂಗ್", "ಟ್ರಾಫಿಕ್ ಸಿಗ್ನಲ್"],
        "ml": ["നടപ്പാത", "റോഡ് ഡിവൈഡർ", "റെയിലിംഗ്", "ഗാർഡ് റെയിൽ", "ബസ് ഷെൽട്ടർ", "സ്പീഡ് ബ്രേക്കർ", "റോഡ് സൈൻ", "സീബ്ര ക്രോസിംഗ്", "ട്രാഫിക് സിഗ്നൽ"],
        "or": ["ଫୁଟପାଥ", "ରାସ୍ତା ଡିଭାଇଡର", "ରେଲିଂ", "ଗାର୍ଡ ରେଲ", "ବସ ଆଶ୍ରୟ", "ସ୍ପିଡ ବ୍ରେକର", "ରାସ୍ତା ସଙ୍କେତ", "ଜେବ୍ରା କ୍ରସିଂ", "ଟ୍ରାଫିକ ସିଗ୍ନାଲ"],
        "pa": ["ਫੁੱਟਪਾਥ", "ਡਿਵਾਈਡਰ", "ਰੇਲਿੰਗ", "ਗਾਰਡ ਰੇਲ", "ਬੱਸ ਸ਼ੈਲਟਰ", "ਸਪੀਡ ਬ੍ਰੇਕਰ", "ਸੜਕ ਨਿਸ਼ਾਨ", "ਜ਼ੈਬਰਾ ਕਰਾਸਿੰਗ", "ਟ੍ਰੈਫਿਕ ਸਿਗਨਲ"],
        "ur": ["فٹ پاتھ", "ڈوائیڈر", "ریلنگ", "گارڈ ریل", "بس شیڈ", "اسپیڈ بریکر", "سڑک کا نشان", "زیبرا کراسنگ", "ٹریفک سگنل"],
        "ne": ["फुटपाथ", "डिभाइडर", "रेलिङ", "गार्ड रेल", "बस स्टप", "स्पीड ब्रेकर", "सडक चिन्ह", "जेब्रा क्रसिङ", "ट्राफिक सिग्नल"],
    },
    "water_supply": {
        "en": ["water supply", "no water", "water pipeline", "tap water", "water leak", "low water pressure", "contaminated water", "tanker"],
        "hi": ["पानी की सप्लाई", "पानी नहीं", "पानी की पाइपलाइन", "नल का पानी", "पानी का रिसाव", "कम दबाव", "दूषित पानी", "टैंकर", "pani nahi", "pani ki supply", "pani ki pipeline", "pani leak"],
        "mr": ["पाणी पुरवठा", "पाणी येत नाही", "पाण्याची पाइपलाइन", "नळाचे पाणी", "पाण्याची गळती", "कमी दाब", "दूषित पाणी", "टँकर", "pani purvatha", "pani yet nahi", "panyachi pipeline", "panyachi galti", "tanker"],
        "gu": ["પાણી પુરવઠો", "પાણી આવતું નથી", "પાણીની પાઇપલાઇન", "નળનું પાણી", "પાણી લીક", "ઓછું દબાણ", "દૂષિત પાણી", "ટેન્કર"],
        "bn": ["জল সরবরাহ", "জল নেই", "জলের পাইপলাইন", "কলের জল", "জল লিক", "কম চাপ", "দূষিত জল", "ট্যাঙ্কার"],
        "ta": ["குடிநீர் வழங்கல்", "தண்ணீர் வரவில்லை", "தண்ணீர் குழாய்", "குழாய் நீர்", "தண்ணீர் கசிவு", "குறைந்த அழுத்தம்", "மாசான நீர்", "டேங்கர்"],
        "te": ["నీటి సరఫరా", "నీరు రావడం లేదు", "నీటి పైప్‌లైన్", "కుళాయి నీరు", "నీరు లీక్", "తక్కువ ఒత్తిడి", "కలుషిత నీరు", "ట్యాంకర్"],
        "kn": ["ನೀರಿನ ಪೂರೈಕೆ", "ನೀರು ಬರುತ್ತಿಲ್ಲ", "ನೀರಿನ ಪೈಪ್‌ಲೈನ್", "ಕೊಳವೆ ನೀರು", "ನೀರು ಸೋರಿಕೆ", "ಕಡಿಮೆ ಒತ್ತಡ", "ಕಲುಷಿತ ನೀರು", "ಟ್ಯಾಂಕರ್"],
        "ml": ["ജലവിതരണം", "വെള്ളം വരുന്നില്ല", "വാട്ടർ പൈപ്പ്", "ടാപ്പ് വെള്ളം", "വെള്ളം ചോർച്ച", "കുറഞ്ഞ മർദ്ദം", "മലിനജലം", "ടാങ്കർ"],
        "or": ["ଜଳ ଯୋଗାଣ", "ପାଣି ଆସୁନାହିଁ", "ପାଣି ପାଇପ", "ନଳ ପାଣି", "ପାଣି ଲିକ", "କମ ଚାପ", "ଦୂଷିତ ପାଣି", "ଟ୍ୟାଙ୍କର"],
        "pa": ["ਪਾਣੀ ਦੀ ਸਪਲਾਈ", "ਪਾਣੀ ਨਹੀਂ ਆ ਰਿਹਾ", "ਪਾਣੀ ਦੀ ਪਾਈਪ", "ਨਲ ਦਾ ਪਾਣੀ", "ਪਾਣੀ ਲੀਕ", "ਘੱਟ ਦਬਾਅ", "ਗੰਦਾ ਪਾਣੀ", "ਟੈਂਕਰ"],
        "ur": ["پانی کی فراہمی", "پانی نہیں آ رہا", "پانی کی پائپ لائن", "نل کا پانی", "پانی لیک", "کم دباؤ", "آلودہ پانی", "ٹینکر"],
        "ne": ["खानेपानी", "पानी आएको छैन", "पानीको पाइप", "धाराको पानी", "पानी चुहावट", "कम दबाब", "दूषित पानी", "ट्यांकर"],
    },
}

SEVERITY_LEXICON = {
    "en": [
        ("critical", 2), ("dangerous", 2), ("urgent", 2), ("accident", 2),
        ("collapsed", 2), ("burst", 2), ("flooding", 2), ("sparking", 2),
        ("severe", 2), ("deep", 1), ("huge", 2), ("large", 1),
        ("unsafe", 1), ("hazard", 1), ("broken", 1), ("overflowing", 1),
    ],
    "hi": [("खतरनाक", 2), ("तुरंत", 2), ("दुर्घटना", 2), ("बाढ़", 2), ("बहुत बड़ा", 2), ("गहरा", 1), ("टूटा", 1), ("असुरक्षित", 1)],
    "mr": [("धोकादायक", 2), ("तातडीचे", 2), ("अपघात", 2), ("पूर", 2), ("खूप मोठा", 2), ("खोल", 1), ("तुटलेला", 1), ("असुरक्षित", 1), ("ओसंडून", 1)],
    "gu": [("જોખમી", 2), ("તાત્કાલિક", 2), ("અકસ્મા", 2), ("પૂર", 2), ("ખૂબ મોટો", 2), ("ઊંડો", 1), ("તૂટેલો", 1), ("અસુરક્ષિત", 1)],
    "bn": [("বিপজ্জনক", 2), ("জরুরি", 2), ("দুর্ঘটনা", 2), ("বন্যা", 2), ("বড়", 1), ("গভীর", 1), ("ভাঙা", 1)],
    "ta": [("ஆபத்தான", 2), ("அவசரம்", 2), ("விபத்து", 2), ("வெள்ளம்", 2), ("பெரிய", 1), ("ஆழமான", 1), ("உடைந்த", 1)],
    "te": [("ప్రమాదకరమైన", 2), ("అత్యవసరం", 2), ("ప్రమాదం", 2), ("వరద", 2), ("పెద్ద", 1), ("లోతైన", 1), ("విరిగిన", 1)],
    "kn": [("ಅಪಾಯಕಾರಿ", 2), ("ತುರ್ತು", 2), ("ಅಪಘಾತ", 2), ("ಪ್ರವಾಹ", 2), ("ದೊಡ್ಡ", 1), ("ಆಳವಾದ", 1), ("ಮುರಿದ", 1)],
    "ml": [("അപകടകരമായ", 2), ("അടിയന്തിരം", 2), ("അപകടം", 2), ("വെള്ളപ്പൊക്കം", 2), ("വലിയ", 1), ("ആഴമുള്ള", 1), ("തകർന്ന", 1)],
    "or": [("ବିପଦଜନକ", 2), ("ଜରୁରୀ", 2), ("ଦୁର୍ଘଟଣା", 2), ("ବନ୍ୟା", 2), ("ବଡ", 1), ("ଗଭୀର", 1), ("ଭଙ୍ଗା", 1)],
    "pa": [("ਖਤਰਨਾਕ", 2), ("ਤੁਰੰਤ", 2), ("ਹਾਦਸਾ", 2), ("ਹੜ੍ਹ", 2), ("ਵੱਡਾ", 1), ("ਡੂੰਘਾ", 1), ("ਟੁੱਟਿਆ", 1)],
    "ur": [("خطرناک", 2), ("فوری", 2), ("حادثہ", 2), ("سیلاب", 2), ("بڑا", 1), ("گہرا", 1), ("ٹوٹا", 1)],
}


# Native-language examples used to fit the local character model. The English
# examples remain in training_data.py; this set supplies linguistic coverage.
MULTILINGUAL_TRAINING_EXAMPLES = [
    # Marathi
    ("रस्त्यावर मोठा खड्डा आहे", "pothole"),
    ("रस्त्यात खड्डे पडले आहेत", "pothole"),
    ("कचरा अनेक दिवसांपासून उचललेला नाही", "garbage"),
    ("कचर्‍याचा मोठा ढिग रस्त्यावर आहे", "garbage"),
    ("पथदिवा अनेक दिवसांपासून बंद आहे", "streetlight"),
    ("रस्त्यावरील दिवा लागत नाही", "streetlight"),
    ("नाला तुंबला आहे आणि पाणी साचले आहे", "drainage"),
    ("गटारातून सांडपाणी रस्त्यावर येत आहे", "drainage"),
    ("आमच्या भागात पाणी येत नाही", "water_supply"),
    ("पाण्याच्या पाइपमधून गळती होत आहे", "water_supply"),
    ("रस्त्याचा डिव्हायडर तुटला आहे", "road_infrastructure"),
    ("फुटपाथची रेलिंग मोडली आहे", "road_infrastructure"),
    # Hindi
    ("सड़क पर बड़ा गड्ढा है", "pothole"),
    ("सड़क में कई गड्ढे हैं", "pothole"),
    ("कचरा कई दिनों से नहीं उठाया गया", "garbage"),
    ("सड़क के पास कूड़े का ढेर है", "garbage"),
    ("स्ट्रीट लाइट कई दिनों से बंद है", "streetlight"),
    ("सड़क की बत्ती काम नहीं कर रही", "streetlight"),
    ("नाली बंद है और पानी भर गया है", "drainage"),
    ("गटर का गंदा पानी सड़क पर आ रहा है", "drainage"),
    ("हमारे इलाके में पानी नहीं आ रहा", "water_supply"),
    ("पानी की पाइपलाइन में रिसाव है", "water_supply"),
    ("सड़क का डिवाइडर टूट गया है", "road_infrastructure"),
    ("फुटपाथ की रेलिंग टूटी है", "road_infrastructure"),
    # Gujarati
    ("રસ્તા પર મોટો ખાડો છે", "pothole"),
    ("રસ્તામાં ઘણા ખાડા છે", "pothole"),
    ("ઘણા દિવસથી કચરો ઉઠાવવામાં આવ્યો નથી", "garbage"),
    ("રસ્તા પાસે કચરાનો ઢગલો છે", "garbage"),
    ("સ્ટ્રીટ લાઇટ ઘણા દિવસથી બંધ છે", "streetlight"),
    ("રસ્તાની લાઇટ કામ કરતી નથી", "streetlight"),
    ("નાળો બંધ છે અને પાણી ભરાય છે", "drainage"),
    ("ગટરમાંથી ગંદુ પાણી રસ્તા પર આવે છે", "drainage"),
    ("અમારા વિસ્તારમાં પાણી આવતું નથી", "water_supply"),
    ("પાણીની પાઇપલાઇનમાં લીક છે", "water_supply"),
    ("રસ્તાનો ડિવાઇડર તૂટી ગયો છે", "road_infrastructure"),
    ("ફૂટપાથની રેલિંગ તૂટી છે", "road_infrastructure"),
    # Bengali
    ("রাস্তায় বড় গর্ত হয়েছে", "pothole"),
    ("রাস্তায় অনেক গর্ত আছে", "pothole"),
    ("অনেক দিন ধরে আবর্জনা তোলা হয়নি", "garbage"),
    ("রাস্তায় আবর্জনার স্তূপ আছে", "garbage"),
    ("স্ট্রিট লাইট কয়েক দিন ধরে বন্ধ", "streetlight"),
    ("রাস্তার আলো কাজ করছে না", "streetlight"),
    ("নালা বন্ধ হয়ে জল জমেছে", "drainage"),
    ("নর্দমার জল রাস্তায় আসছে", "drainage"),
    ("আমাদের এলাকায় জল আসছে না", "water_supply"),
    ("জলের পাইপে লিক হয়েছে", "water_supply"),
    ("রাস্তার ডিভাইডার ভেঙে গেছে", "road_infrastructure"),
    ("ফুটপাতের রেলিং ভাঙা", "road_infrastructure"),
    # Tamil
    ("சாலையில் பெரிய பள்ளம் உள்ளது", "pothole"),
    ("சாலையில் பல பள்ளங்கள் உள்ளன", "pothole"),
    ("பல நாட்களாக குப்பை எடுக்கப்படவில்லை", "garbage"),
    ("சாலையில் குப்பை குவிந்து கிடக்கிறது", "garbage"),
    ("தெருவிளக்கு பல நாட்களாக எரியவில்லை", "streetlight"),
    ("சாலை விளக்கு வேலை செய்யவில்லை", "streetlight"),
    ("வடிகால் அடைந்ததால் தண்ணீர் தேங்கியுள்ளது", "drainage"),
    ("சாக்கடை நீர் சாலையில் வருகிறது", "drainage"),
    ("எங்கள் பகுதியில் தண்ணீர் வரவில்லை", "water_supply"),
    ("தண்ணீர் குழாயில் கசிவு உள்ளது", "water_supply"),
    ("சாலை பிரிப்பான் உடைந்துவிட்டது", "road_infrastructure"),
    ("நடைபாதை ரெயிலிங் உடைந்துள்ளது", "road_infrastructure"),
    # Telugu
    ("రోడ్డుపై పెద్ద గుంత ఉంది", "pothole"),
    ("రోడ్డులో చాలా గుంతలు ఉన్నాయి", "pothole"),
    ("చాలా రోజులుగా చెత్త తీసుకెళ్లలేదు", "garbage"),
    ("రోడ్డుపక్కన చెత్త కుప్ప ఉంది", "garbage"),
    ("స్ట్రీట్ లైట్ చాలా రోజులుగా పనిచేయడం లేదు", "streetlight"),
    ("రోడ్డు లైట్ ఆఫ్ అయింది", "streetlight"),
    ("కాలువ మూసుకుపోయి నీరు నిలిచిపోయింది", "drainage"),
    ("మురుగునీరు రోడ్డుపైకి వస్తోంది", "drainage"),
    ("మా ప్రాంతంలో నీరు రావడం లేదు", "water_supply"),
    ("నీటి పైప్‌లో లీక్ ఉంది", "water_supply"),
    ("రోడ్డు డివైడర్ విరిగిపోయింది", "road_infrastructure"),
    ("ఫుట్‌పాత్ రైలింగ్ విరిగింది", "road_infrastructure"),
    # Kannada
    ("ರಸ್ತೆಯಲ್ಲಿ ದೊಡ್ಡ ಗುಂಡಿ ಇದೆ", "pothole"),
    ("ರಸ್ತೆಯಲ್ಲಿ ಹಲವಾರು ಗುಂಡಿಗಳಿವೆ", "pothole"),
    ("ಹಲವು ದಿನಗಳಿಂದ ಕಸ ತೆಗೆದುಕೊಂಡಿಲ್ಲ", "garbage"),
    ("ರಸ್ತೆಯ ಬಳಿ ಕಸದ ರಾಶಿ ಇದೆ", "garbage"),
    ("ಬೀದಿ ದೀಪ ಹಲವು ದಿನಗಳಿಂದ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", "streetlight"),
    ("ರಸ್ತೆ ದೀಪ ಆರಿದೆ", "streetlight"),
    ("ಚರಂಡಿ ಮುಚ್ಚಿ ನೀರು ನಿಂತಿದೆ", "drainage"),
    ("ಚರಂಡಿಯ ಕೊಳಚೆ ನೀರು ರಸ್ತೆಗೆ ಬರುತ್ತಿದೆ", "drainage"),
    ("ನಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ನೀರು ಬರುತ್ತಿಲ್ಲ", "water_supply"),
    ("ನೀರಿನ ಪೈಪ್‌ನಲ್ಲಿ ಸೋರಿಕೆ ಇದೆ", "water_supply"),
    ("ರಸ್ತೆ ಡಿವೈಡರ್ ಮುರಿದಿದೆ", "road_infrastructure"),
    ("ಪಾದಚಾರಿ ಮಾರ್ಗದ ರೇಲಿಂಗ್ ಮುರಿದಿದೆ", "road_infrastructure"),
    # Malayalam
    ("റോഡിൽ വലിയ കുഴിയുണ്ട്", "pothole"),
    ("റോഡിൽ നിരവധി കുഴികളുണ്ട്", "pothole"),
    ("പല ദിവസമായി മാലിന്യം എടുത്തിട്ടില്ല", "garbage"),
    ("റോഡരികിൽ മാലിന്യക്കൂമ്പാരം ഉണ്ട്", "garbage"),
    ("തെരുവ് വിളക്ക് പല ദിവസമായി കത്തുന്നില്ല", "streetlight"),
    ("റോഡ് ലൈറ്റ് പ്രവർത്തിക്കുന്നില്ല", "streetlight"),
    ("ഓട അടഞ്ഞ് വെള്ളക്കെട്ടായി", "drainage"),
    ("മലിനജലം റോഡിലേക്ക് വരുന്നു", "drainage"),
    ("ഞങ്ങളുടെ പ്രദേശത്ത് വെള്ളം വരുന്നില്ല", "water_supply"),
    ("വാട്ടർ പൈപ്പിൽ ചോർച്ചയുണ്ട്", "water_supply"),
    ("റോഡ് ഡിവൈഡർ തകർന്നിരിക്കുന്നു", "road_infrastructure"),
    ("നടപ്പാതയിലെ റെയിലിംഗ് തകർന്നിട്ടുണ്ട്", "road_infrastructure"),
    # Odia
    ("ରାସ୍ତାରେ ବଡ ଗାତ ଅଛି", "pothole"),
    ("ରାସ୍ତାରେ ଅନେକ ଗାତ ଅଛି", "pothole"),
    ("କେତେ ଦିନ ହେଲା ଆବର୍ଜନା ଉଠାଯାଇନାହିଁ", "garbage"),
    ("ରାସ୍ତା ପାଖରେ କଚରା ଜମିଛି", "garbage"),
    ("ଷ୍ଟ୍ରିଟ ଲାଇଟ କିଛି ଦିନ ଧରି ବନ୍ଦ", "streetlight"),
    ("ରାସ୍ତା ଆଲୋକ କାମ କରୁନାହିଁ", "streetlight"),
    ("ନାଳା ବନ୍ଦ ହୋଇ ପାଣି ଜମିଛି", "drainage"),
    ("ନାଳାର ଦୁଷିତ ପାଣି ରାସ୍ତାକୁ ଆସୁଛି", "drainage"),
    ("ଆମ ଅଞ୍ଚଳରେ ପାଣି ଆସୁନାହିଁ", "water_supply"),
    ("ପାଣି ପାଇପରେ ଲିକ ଅଛି", "water_supply"),
    ("ରାସ୍ତା ଡିଭାଇଡର ଭାଙ୍ଗିଯାଇଛି", "road_infrastructure"),
    ("ଫୁଟପାଥ ରେଲିଂ ଭାଙ୍ଗିଛି", "road_infrastructure"),
    # Punjabi
    ("ਸੜਕ ਤੇ ਵੱਡਾ ਖੱਡਾ ਹੈ", "pothole"),
    ("ਸੜਕ ਵਿੱਚ ਕਈ ਖੱਡੇ ਹਨ", "pothole"),
    ("ਕਈ ਦਿਨਾਂ ਤੋਂ ਕੂੜਾ ਨਹੀਂ ਚੁੱਕਿਆ ਗਿਆ", "garbage"),
    ("ਸੜਕ ਕਿਨਾਰੇ ਕੂੜੇ ਦਾ ਢੇਰ ਹੈ", "garbage"),
    ("ਸਟ੍ਰੀਟ ਲਾਈਟ ਕਈ ਦਿਨਾਂ ਤੋਂ ਬੰਦ ਹੈ", "streetlight"),
    ("ਸੜਕ ਦੀ ਬੱਤੀ ਕੰਮ ਨਹੀਂ ਕਰ ਰਹੀ", "streetlight"),
    ("ਨਾਲਾ ਬੰਦ ਹੈ ਅਤੇ ਪਾਣੀ ਖੜ੍ਹਾ ਹੈ", "drainage"),
    ("ਗਟਰ ਦਾ ਗੰਦਾ ਪਾਣੀ ਸੜਕ ਉੱਤੇ ਆ ਰਿਹਾ ਹੈ", "drainage"),
    ("ਸਾਡੇ ਇਲਾਕੇ ਵਿੱਚ ਪਾਣੀ ਨਹੀਂ ਆ ਰਿਹਾ", "water_supply"),
    ("ਪਾਣੀ ਦੀ ਪਾਈਪ ਲੀਕ ਕਰ ਰਹੀ ਹੈ", "water_supply"),
    ("ਸੜਕ ਦਾ ਡਿਵਾਈਡਰ ਟੁੱਟ ਗਿਆ ਹੈ", "road_infrastructure"),
    ("ਫੁੱਟਪਾਥ ਦੀ ਰੇਲਿੰਗ ਟੁੱਟੀ ਹੈ", "road_infrastructure"),
    # Urdu
    ("سڑک پر بڑا گڑھا ہے", "pothole"),
    ("سڑک میں بہت سے گڑھے ہیں", "pothole"),
    ("کئی دن سے کچرا نہیں اٹھایا گیا", "garbage"),
    ("سڑک کے کنارے کچرے کا ڈھیر ہے", "garbage"),
    ("اسٹریٹ لائٹ کئی دن سے بند ہے", "streetlight"),
    ("سڑک کی بتی کام نہیں کر رہی", "streetlight"),
    ("نالہ بند ہے اور پانی کھڑا ہے", "drainage"),
    ("گٹر کا گندا پانی سڑک پر آ رہا ہے", "drainage"),
    ("ہمارے علاقے میں پانی نہیں آ رہا", "water_supply"),
    ("پانی کی پائپ لائن میں لیک ہے", "water_supply"),
    ("سڑک کا ڈوائیڈر ٹوٹ گیا ہے", "road_infrastructure"),
    ("فٹ پاتھ کی ریلنگ ٹوٹی ہوئی ہے", "road_infrastructure"),
    # English support for the multilingual model as a calibration anchor.
    ("there is a large pothole on the road", "pothole"),
    ("garbage has not been collected for days", "garbage"),
    ("the streetlight is not working", "streetlight"),
    ("the drain is blocked and water is overflowing", "drainage"),
    ("there is no water supply in our area", "water_supply"),
    ("the road divider is damaged", "road_infrastructure"),
]


@dataclass(frozen=True)
class LanguageDetection:
    code: str
    name: str
    confidence: float
    source: str


def _script_counts(text: str) -> Counter:
    counts = Counter()
    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            counts["devanagari"] += 1
        elif 0x0A80 <= code <= 0x0AFF:
            counts["gujarati"] += 1
        elif 0x0980 <= code <= 0x09FF:
            counts["bengali"] += 1
        elif 0x0B00 <= code <= 0x0B7F:
            counts["odia"] += 1
        elif 0x0B80 <= code <= 0x0BFF:
            counts["tamil"] += 1
        elif 0x0C00 <= code <= 0x0C7F:
            counts["telugu"] += 1
        elif 0x0C80 <= code <= 0x0CFF:
            counts["kannada"] += 1
        elif 0x0D00 <= code <= 0x0D7F:
            counts["malayalam"] += 1
        elif 0x0A00 <= code <= 0x0A7F:
            counts["gurmukhi"] += 1
        elif 0x0600 <= code <= 0x06FF:
            counts["arabic"] += 1
    return counts


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", text.lower(), flags=re.UNICODE)


def _phrase_matches(text: str, phrase: str) -> int:
    return text.lower().count(phrase.lower())


def detect_language(text: str, hint: Optional[str] = None) -> LanguageDetection:
    cleaned = (text or "").strip()
    normalized_hint = (hint or "").lower().strip()
    if normalized_hint not in LANGUAGE_NAMES:
        normalized_hint = ""

    scripts = _script_counts(cleaned)
    if scripts:
        script, count = scripts.most_common(1)[0]
        total = sum(scripts.values()) or 1
        ratio = count / total
        mapping = {
            "gujarati": "gu",
            "bengali": "bn",
            "tamil": "ta",
            "telugu": "te",
            "kannada": "kn",
            "malayalam": "ml",
            "odia": "or",
            "gurmukhi": "pa",
            "arabic": "ur",
        }
        if script in mapping:
            code = mapping[script]
            return LanguageDetection(code, LANGUAGE_NAMES[code], round(min(0.99, 0.82 + ratio * 0.17), 4), "unicode-script")

        if script == "devanagari":
            markers = {
                "mr": ["आमच्या", "आहे", "नाही", "रस्त्यावर", "खूप", "पाणी", "कचरा", "पथदिवा", "नाला", "तुंबला"],
                "hi": ["हमारे", "है", "नहीं", "सड़क", "बहुत", "पानी", "कचरा", "स्ट्रीट", "नाली", "बंद"],
                "ne": ["हाम्रो", "छ", "छैन", "सडक", "पानी", "फोहोर", "बत्ती"],
                "sa": ["अस्ति", "अत्र", "जलम्", "मार्गः"],
                "mai": ["हमर", "अछि", "नहि", "पानि", "कचरा"],
                "doi": ["सड़क", "पानी", "गड्डा", "नै", "आं"],
            }
            scores = {lang: sum(_phrase_matches(cleaned, marker) for marker in markers) for lang, markers in markers.items()}
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                confidence = 0.78 if normalized_hint == best else 0.84
                return LanguageDetection(best, LANGUAGE_NAMES.get(best, best), confidence, "script-plus-vocabulary")
            if normalized_hint in {"hi", "mr", "ne", "sa", "mai", "doi"}:
                return LanguageDetection(normalized_hint, LANGUAGE_NAMES.get(normalized_hint, normalized_hint), 0.72, "language-hint")
            return LanguageDetection("hi", "Hindi", 0.52, "script-family-fallback")

    # Latin-script input is common for English and transliterated Indian speech.
    if normalized_hint and not scripts:
        return LanguageDetection(normalized_hint, LANGUAGE_NAMES[normalized_hint], 0.74, "language-hint")

    tokens = set(_tokenize(cleaned))
    english_markers = {"the", "is", "are", "road", "water", "garbage", "light", "drain", "pothole", "not", "working"}
    overlap = len(tokens & english_markers)
    confidence = min(0.95, 0.62 + overlap * 0.06)
    return LanguageDetection("en", "English", round(confidence, 4), "latin-default")


def canonical_terms(text: str, language: Optional[str] = None) -> dict[str, int]:
    """Return category => match count using language-aware civic vocabulary."""
    cleaned = (text or "").strip().lower()
    detected = detect_language(cleaned, language).code
    scores: dict[str, int] = {}

    languages_to_check = [detected]
    if "en" not in languages_to_check:
        languages_to_check.append("en")

    for category, by_language in CATEGORY_LEXICON.items():
        count = 0
        for lang in languages_to_check:
            for phrase in by_language.get(lang, []):
                count += _phrase_matches(cleaned, phrase)
        if count:
            scores[category] = count
    return scores


def normalize_to_english(text: str, language: Optional[str] = None) -> str:
    """Create a compact English/canonical representation for downstream ML."""
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""

    detected = detect_language(cleaned, language).code
    tags: list[str] = []
    category_scores = canonical_terms(cleaned, detected)
    for category, count in sorted(category_scores.items(), key=lambda item: item[1], reverse=True):
        tags.extend([category.replace("_", " ")] * min(3, count))

    severity_terms: list[str] = []
    for lang in [detected, "en"]:
        for phrase, points in SEVERITY_LEXICON.get(lang, []):
            if _phrase_matches(cleaned, phrase):
                severity_terms.extend(["severe"] * max(1, points))

    tag_text = " ".join(tags + severity_terms)
    return f"{cleaned} {tag_text}".strip() if tag_text else cleaned


def key_civic_terms(text: str, language: Optional[str] = None, top_n: int = 5) -> list[str]:
    scores = canonical_terms(text, language)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [category.replace("_", " ") for category, _ in ordered[:top_n]]


def severity_hint(text: str, language: Optional[str] = None) -> int:
    detected = detect_language(text, language).code
    score = 2
    for lang in [detected, "en"]:
        for phrase, points in SEVERITY_LEXICON.get(lang, []):
            score += _phrase_matches(text, phrase) * points
    return max(1, min(5, score))
