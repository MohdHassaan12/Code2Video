"""Unit 1 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit1 import L

T = {
    "01": ("अपने phone की screen का outline देखिए। अब एक floor tile, और अपनी notebook का एक page। हर outline पर "
           "अपनी उंगली फेरिए। इन सबकी sides सीधी हैं, और हर एक की four sides हैं।",
           ["phone की screen का outline", "इन सबकी sides सीधी हैं", "हर एक की four sides हैं"], None),
    "02": ("यहाँ three shapes हैं: एक square, एक triangle और एक bow-tie. इनमें से सिर्फ़ एक quadrilateral है। "
           "वो कौन सा है?",
           ["एक square, एक triangle और एक bow-tie"],
           ("कौन सी shape quadrilateral है?", ["square", "triangle", "bow-tie"],
            ["हाँ। four सीधी sides, जो बंद shape बनाती हैं और एक-दूसरे को कभी cross नहीं करतीं।",
             "इसकी sides गिनिए: triangle की सिर्फ़ three sides होती हैं।",
             "इसकी four sides हैं, पर बीच में two sides एक-दूसरे को cross करती हैं। वहाँ ध्यान से देखिए।"])),
    "03": ("जवाब है square. Triangle की सिर्फ़ three sides हैं। Bow-tie की four sides तो हैं, पर बीच में देखिए। "
           "वहाँ इसकी two sides एक-दूसरे को cross करती हैं, ऐसे point पर जो corner नहीं है। इसकी boundary खुद को "
           "cross करती है, इसलिए ये quadrilateral नहीं है।",
           ["Triangle की सिर्फ़ three sides हैं", "इसकी two sides एक-दूसरे को cross करती हैं",
            "इसलिए ये quadrilateral नहीं है"], None),
    "04": ("तो हमारी definition ये है। Quadrilateral एक बंद shape है, एक flat surface पर, जो four सीधी sides से "
           "बनती है। Sides सिर्फ़ अपने ends पर मिलती हैं, हर corner पर two, और कोई side दूसरी side को cross नहीं करती।",
           ["एक बंद shape है, एक flat surface पर", "four सीधी sides से बनती है", "सिर्फ़ अपने ends पर मिलती हैं",
            "कोई side दूसरी side को cross नहीं करती"], None),
    "05": ("अब अपनी shape को नाम देते हैं। ये quadrilateral A B C D है। इसके four corners, A, B, C और D, इसके "
           "vertices कहलाते हैं। एक corner को vertex कहते हैं।",
           ["ये quadrilateral A B C D है", "vertices कहलाते हैं", "एक corner को vertex कहते हैं"], None),
    "06": ("इसकी sides हैं AB, BC, CD और DA. इन्हें क्रम से पढ़िए, तो आप boundary के चारों ओर घूम लेते हैं: "
           "A से B, फिर C, फिर D, और वापस A पर, जहाँ से शुरू किया था।",
           ["इसकी sides हैं AB, BC, CD और DA", "boundary के चारों ओर घूम लेते हैं"], None),
    "07": ("अब side AB और side BC को देखिए। दोनों B पर खत्म होती हैं। जो two sides एक endpoint share करती हैं, "
           "उन्हें adjacent sides कहते हैं।",
           ["दोनों B पर खत्म होती हैं", "उन्हें adjacent sides कहते हैं"], None),
    "08": ("Side AB और side CD का कोई भी endpoint common नहीं है। ये आमने-सामने हैं, इसलिए ये opposite sides हैं। "
           "इसी तरह, BC और DA भी opposite sides हैं।",
           ["कोई भी endpoint common नहीं है", "इसलिए ये opposite sides हैं", "BC और DA भी opposite sides हैं"], None),
    "09": ("अब आपकी बारी। Side BC के opposite कौन सी side है?",
           ["Side BC के opposite कौन सी side है"],
           ("BC के opposite कौन सी side है?", ["DA", "AB", "CD"],
            ["हाँ। BC के ends B और C हैं; DA के ends D और A हैं, कुछ भी common नहीं।",
             "AB और BC का endpoint B common है, इसलिए AB, BC की adjacent side है।",
             "CD और BC का endpoint C common है, इसलिए CD, BC की adjacent side है।"])),
    "10": ("जवाब है DA. BC में points B और C हैं, और DA में D और A, तो कोई endpoint common नहीं। AB और CD दोनों "
           "BC को छूती हैं, इसलिए वो उसकी adjacent sides हैं।",
           ["जवाब है DA", "इसलिए वो उसकी adjacent sides हैं"], None),
    "11": ("हर vertex पर shape के अंदर एक angle भी होता है: angle A, angle B, angle C और angle D. Angle A और "
           "angle C opposite angles हैं। Angle A और angle B adjacent angles हैं।",
           ["हर vertex पर shape के अंदर एक angle भी होता है", "Angle A और angle C opposite angles हैं",
            "Angle A और angle B adjacent angles हैं"], None),
    "12": ("अब A को C से जोड़िए। Boundary पर A और C पास-पास नहीं हैं, इसलिए AC कोई side नहीं है। ऐसा segment, जो "
           "two ऐसे vertices को जोड़ता है जो पड़ोसी नहीं हैं, diagonal कहलाता है।",
           ["A को C से जोड़िए", "इसलिए AC कोई side नहीं है", "diagonal कहलाता है"], None),
    "13": ("मेरे draw करने से पहले, अंदाज़ा लगाइए। दूसरा diagonal कौन सा है?",
           ["दूसरा diagonal कौन सा है"],
           ("दूसरा diagonal कौन सा है?", ["BD", "AB", "CA"],
            ["हाँ। B और D बचे हुए two vertices हैं, जो पड़ोसी नहीं हैं।",
             "AB एक side है: boundary पर A और B पड़ोसी हैं।",
             "CA वही diagonal है जो AC है, बस उल्टा पढ़ा गया है।"])),
    "14": ("जवाब है BD. ये बाकी two vertices को जोड़ता है जो पड़ोसी नहीं हैं। हर quadrilateral के ठीक two "
           "diagonals होते हैं।",
           ["जवाब है BD", "ठीक two diagonals होते हैं"], None),
    "15": ("एक बात और: नाम। Quadrilateral का नाम हम उसकी boundary पर क्रम से चलकर रखते हैं। A B C D सही है। "
           "B C D A भी सही है, और D C B A भी, जो उल्टी दिशा में चलता है। पर देखिए A C B D क्या करता है। ये diagonal "
           "पर कूद जाता है, और इसका रास्ता खुद को cross करता है।",
           ["boundary पर क्रम से चलकर", "B C D A भी सही है", "ये diagonal पर कूद जाता है"], None),
    "16": ("एक करके देखिए। क्या A D C B हमारे quadrilateral का सही नाम है?",
           ["क्या A D C B हमारे quadrilateral का सही नाम है"],
           ("क्या ADCB, ABCD का सही नाम है?", ["हाँ", "नहीं"],
            ["हाँ। A से D, D से C, C से B, B से A: हर कदम एक side है, बस उल्टी दिशा में।",
             "हर कदम check कीजिए: AD, DC, CB और BA सब sides हैं, तो ये रास्ता boundary के चारों ओर ही जाता है।"])),
    "17": ("हाँ, है। A से D एक side है, D से C एक side है, C से B एक side है, और B से वापस A भी एक side है। "
           "A D C B वही boundary है, बस उल्टी दिशा में।",
           ["A से D एक side है", "बस उल्टी दिशा में"], None),
    "18": ("चलिए देखते हैं आपने क्या सीखा। ये रहीं वही three shapes. किसकी four sides हैं, फिर भी वो हमारी "
           "definition को तोड़ती है?",
           ["ये रहीं वही three shapes"],
           ("किस shape की four sides हैं, पर वो quadrilateral नहीं है?", ["bow-tie", "square", "triangle"],
            ["हाँ। इसकी sides एक ऐसे point पर cross करती हैं जो corner नहीं है।",
             "Square हर नियम मानता है: four sides, जो सिर्फ़ अपने ends पर मिलती हैं।",
             "Triangle किसी और वजह से बाहर है: उसकी three sides हैं, four नहीं।"])),
    "19": ("जवाब है bow-tie. इसकी sides corners के बीच में cross करती हैं, और हमारी definition कहती है कि sides "
           "सिर्फ़ अपने ends पर मिल सकती हैं।",
           ["जवाब है bow-tie", "सिर्फ़ अपने ends पर मिल सकती हैं"], None),
    "20": ("तो, short में। Quadrilateral के four vertices, four sides, four angles और two diagonals होते हैं। Adjacent "
           "sides एक vertex share करती हैं। Opposite sides नहीं करतीं। और shape का नाम हम उसकी boundary पर क्रम से "
           "चलकर रखते हैं।",
           ["four vertices, four sides, four angles और two diagonals", "Adjacent sides एक vertex share करती हैं",
            "Opposite sides नहीं करतीं", "boundary पर क्रम से चलकर रखते हैं"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 1 (Hindi): what a quadrilateral is")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u1_hi.json")
