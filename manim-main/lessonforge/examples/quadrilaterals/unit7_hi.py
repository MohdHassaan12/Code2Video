"""Unit 7 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit7 import L

T = {
    "01": ("Median, triangle के एक corner को सामने वाली side के midpoint से जोड़ता है। यहाँ D, BC का midpoint है, तो BD "
           "equal है DC के। A से D तक का segment एक median है।",
           ["triangle के एक corner को", "D, BC का midpoint है", "A से D तक का segment एक median है"], None),
    "02": ("इस triangle में three segments खींचे गए हैं। इनमें से सिर्फ़ एक median है। कौन सा?",
           ["इनमें से सिर्फ़ एक median है", "कौन सा"],
           ("कौन सा segment median है?", ["segment 2", "segment 1", "segment 3"],
            ["हाँ। ये corner A से शुरू होकर D पर खत्म होता है, जो सामने वाली side का midpoint है।",
             "ये BC से right angle पर मिलता है: ये altitude है। इसका पैर BC का midpoint नहीं है।",
             "ये BC को उसके midpoint पर right angle पर काटता है, पर किसी corner से शुरू नहीं होता।"])),
    "03": ("Segment two median है: ये एक corner से शुरू होकर midpoint पर खत्म होता है। Segment one एक altitude है: ये BC "
           "से right angle पर मिलता है, पर midpoint पर नहीं। Segment three एक perpendicular bisector है: ये किसी corner "
           "से शुरू नहीं होता।",
           ["Segment two median है", "Segment one एक altitude है", "Segment three एक perpendicular bisector है"],
           None),
    "04": ("हर triangle के three medians होते हैं, हर corner से एक। बाकी two खींचिए, B से और C से। तीनों एक ही point पर "
           "मिलते हैं, G. उस point को centroid कहते हैं।",
           ["हर triangle के three medians होते हैं", "बाकी two खींचिए", "तीनों एक ही point पर मिलते हैं",
            "उस point को centroid कहते हैं"], None),
    "05": ("Centroid हर median को two to one के ratio में काटता है, corner से नापकर। Median AD पर AG, GD का दोगुना है। "
           "यहाँ GD ten centimetres है, और AG twenty.",
           ["two to one के ratio में", "corner से नापकर", "यहाँ GD ten centimetres है"], None),
    "06": ("अब आपकी बारी। एक दूसरे triangle में, एक median पर GD ten centimetres है। AG कितनी लंबी है?",
           ["एक median पर GD ten centimetres है", "AG कितनी लंबी है"],
           ("G centroid है और GD = 10 cm. AG कितनी लंबी है?", ["20 cm", "5 cm", "30 cm"],
            ["हाँ। Corner वाला हिस्सा बड़ा होता है: AG = 2 × 10 = 20 cm.",
             "ये GD का half है, यानी ratio उल्टा हो गया। Corner को छूने वाला हिस्सा बड़ा होता है।",
             "30 cm पूरा median AD है। AG सिर्फ़ A से G तक का हिस्सा है।"])),
    "07": ("AG twenty centimetres है: corner वाला हिस्सा बड़ा है, तो ten का दोगुना। अब इसे उल्टा कीजिए। अगर AG twenty "
           "centimetres है, तो GD कितनी है?",
           ["ten का दोगुना", "अब इसे उल्टा कीजिए", "तो GD कितनी है"],
           ("G centroid है और AG = 20 cm. GD कितनी लंबी है?", ["10 cm", "40 cm", "20 cm"],
            ["हाँ। GD छोटा हिस्सा है: AG का half, यानी 10 cm.",
             "ये AG का दोगुना है, तो ratio उल्टा हो गया। GD छोटा हिस्सा है।",
             "AG और GD equal नहीं हैं: AG, GD का दोगुना है।"])),
    "08": ("GD ten centimetres है, AG का half। तो पूरा median AD thirty centimetres है: corner से G तक two हिस्से, और G से "
           "side तक एक हिस्सा।",
           ["GD ten centimetres है", "पूरा median AD thirty centimetres है", "corner से G तक two हिस्से"], None),
    "09": ("पहले अंदाज़ा लगाइए। अगर हम corner A को खींचकर triangle को फैला दें, तो क्या AG और GD का ratio अब भी two to "
           "one रहेगा?",
           ["पहले अंदाज़ा लगाइए", "क्या AG और GD का ratio अब भी two to one रहेगा"],
           ("अगर triangle को फैला दें, तो क्या AG : GD अब भी 2 : 1 रहेगा?",
            ["हाँ, 2 : 1 ही रहेगा", "नहीं, shape के साथ बदलेगा", "सिर्फ़ equilateral triangle में"],
            ["चलिए देखते हैं कि picture सहमत है या नहीं।",
             "लंबाइयाँ बदलती हैं, पर triangle फैलते समय ratio पर नज़र रखिए।",
             "हमारा triangle equilateral नहीं है, फिर भी 2 : 1 है। इसे फैलते हुए देखिए।"])),
    "10": ("A को चलते हुए देखिए। Midpoints हिलते हैं, medians हिलते हैं, और G भी उनके साथ हिलता है। AG और GD दोनों की "
           "लंबाई बदलती है, पर AG हमेशा GD का दोगुना रहता है। Ratio two to one ही रहता है।",
           ["A को चलते हुए देखिए", "G भी उनके साथ हिलता है", "AG और GD दोनों की लंबाई बदलती है",
            "Ratio two to one ही रहता है"], None),
    "11": ("लंबाइयाँ बदलीं और ratio नहीं बदला। अब एक और, खुद से। एक median eighteen centimetres लंबा है। Centroid, corner "
           "से कितनी दूर है?",
           ["लंबाइयाँ बदलीं और ratio नहीं बदला", "एक median eighteen centimetres लंबा है",
            "Centroid, corner से कितनी दूर है"],
           ("Median AD, 18 cm लंबा है और G centroid है। AG कितनी लंबी है?", ["12 cm", "9 cm", "6 cm"],
            ["हाँ। 18 को 6 के three equal हिस्सों में बाँटिए: AG उनमें से two है, 12 cm.",
             "ये median को half-half बाँटता है। Centroid इसे two to one में बाँटता है, one to one में नहीं।",
             "6 cm, GD है, छोटा हिस्सा। AG corner वाला हिस्सा है: two हिस्से, 12 cm."])),
    "12": ("Twelve centimetres. Eighteen, six-six के three हिस्सों में बँटता है। AG उनमें से two लेता है, और GD एक।",
           ["six-six के three हिस्सों में बँटता है", "AG उनमें से two लेता है", "और GD एक"], None),
    "13": ("तो, median एक corner को सामने वाली side के midpoint से जोड़ता है। तीनों medians centroid पर मिलते हैं। और "
           "centroid हर median को two to one में काटता है, बड़ा हिस्सा corner की ओर, triangle की shape चाहे जो हो।",
           ["median एक corner को सामने वाली side के midpoint से जोड़ता है", "तीनों medians centroid पर मिलते हैं",
            "centroid हर median को two to one में काटता है", "triangle की shape चाहे जो हो"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 7 (Hindi): medians and the centroid")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u7_hi.json")
