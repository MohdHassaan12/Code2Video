"""Unit 3 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit3 import L

T = {
    "01": ("यहाँ two quadrilaterals हैं। दोनों की four sides हैं। पहले में हर corner बाहर की ओर है। दूसरे में एक corner "
           "अंदर की ओर दबा है, जैसे एक dent.",
           ["दोनों की four sides हैं", "पहले में हर corner बाहर की ओर है", "दूसरे में एक corner अंदर की ओर दबा है"],
           None),
    "02": ("दूसरी shape को देखिए। कौन सा vertex अंदर की ओर दबा है?",
           ["कौन सा vertex अंदर की ओर दबा है"],
           ("दूसरी shape का कौन सा vertex अंदर की ओर दबा है?", ["D", "B", "A", "C"],
            ["हाँ। D पर boundary मुड़कर बीच की ओर अंदर आती है।",
             "B नुकीला सिरा है: वो बाहर की ओर है, अंदर दबा नहीं।",
             "A shape के नीचे है, और बाहर की ओर है।",
             "C shape के ऊपर है, और बाहर की ओर है।"])),
    "03": ("जवाब है D. अब D पर shape के अंदर का angle नापिए। ये two hundred and sixty-two degrees है, सीधे angle से "
           "ज़्यादा। One hundred and eighty degrees से बड़े angle को reflex angle कहते हैं।",
           ["जवाब है D", "अब D पर shape के अंदर का angle नापिए", "reflex angle कहते हैं"], None),
    "04": ("नियम ये है। Quadrilateral convex होता है जब उसका हर interior angle one hundred and eighty degrees से कम हो। "
           "ये concave होता है, जिसे non-convex भी कहते हैं, जब कोई एक interior angle one hundred and eighty degrees "
           "से ज़्यादा हो।",
           ["convex होता है जब उसका हर interior angle", "ये concave होता है, जिसे non-convex भी कहते हैं"], None),
    "05": ("पतली shapes के साथ सावधान रहिए। इस लंबी, चपटी shape को देखिए। ये convex है या concave?",
           ["ये convex है या concave"],
           ("ये लंबा, पतला quadrilateral convex है या concave?", ["convex", "concave"],
            ["हाँ। इसका हर interior angle अब भी 180 degrees से कम है।",
             "पतला होना dent होना नहीं है: हर interior angle को 180 degrees से मिलाकर देखिए।"])),
    "06": ("ये convex है। ये पिचका हुआ दिखता है, पर चारों angles नापिए: हर एक one hundred and eighty degrees से कम है। "
           "पतलेपन से कोई फ़र्क नहीं पड़ता। सिर्फ़ अंदर की ओर दबा corner ही shape को concave बनाता है।",
           ["ये convex है", "पतलेपन से कोई फ़र्क नहीं पड़ता"], None),
    "07": ("एक दूसरा test भी है, diagonals से। Convex shape में दोनों diagonals अंदर रहते हैं, और एक-दूसरे को अंदर ही "
           "cross करते हैं। Concave shape में diagonal AC बाहर से जाता है, और दोनों diagonals एक-दूसरे को cross ही "
           "नहीं करते।",
           ["diagonals से", "एक-दूसरे को अंदर ही cross करते हैं", "diagonal AC बाहर से जाता है"], None),
    "08": ("अब एक experiment. D, diagonal AC की ओर जाएगा, फिर उसके पार। आपको क्या लगता है, shape का क्या होगा?",
           ["D, diagonal AC की ओर जाएगा", "आपको क्या लगता है"],
           ("D, diagonal AC की ओर और फिर उसके पार जाता है। क्या होता है?",
            ["पहले convex, फिर flat, फिर concave", "ये convex ही रहता है", "ये फिर कभी valid नहीं होता"],
            ["हाँ। three phases: convex, एक पल के लिए line पर दबा हुआ, फिर concave.",
             "D पर angle देखिए: D के AC पार करते ही ये 180 degrees से बड़ा हो जाता है।",
             "Line के पार भी boundary खुद को cross नहीं करती, तो shape फिर valid है, बस concave."])),
    "09": ("D पर angle देखिए। D के line तक पहुँचने से पहले shape convex है, और angle बढ़ता है। ठीक line पर, C, D और "
           "A एक line में हैं, और shape दब गई है। D के पार होने के बाद angle one hundred and eighty degrees से "
           "ज़्यादा है, और shape concave है।",
           ["line तक पहुँचने से पहले", "ठीक line पर", "D के पार होने के बाद"], None),
    "10": ("तो three phases हैं। Line से पहले, convex. Line पर, quadrilateral बिल्कुल नहीं। Line के पार, concave. और "
           "अगर D इतना आगे चला जाए कि two sides cross करने लगें, तो वो एक अलग failure होगा, self-intersecting, सिर्फ़ "
           "concave नहीं।",
           ["तो three phases हैं", "तो वो एक अलग failure होगा"], None),
    "11": ("किसी quadrilateral के चारों interior angles जोड़िए, तो हमेशा three hundred and sixty degrees आता है। वजह "
           "ये है। Diagonal AC इस convex shape को two triangles में बाँटता है। हर triangle के angles का sum one "
           "hundred and eighty degrees है, और two triangles से three hundred and sixty बनता है।",
           ["हमेशा three hundred and sixty degrees आता है", "इस convex shape को two triangles में बाँटता है",
            "two triangles से three hundred and sixty बनता है"], None),
    "12": ("ये concave shape के लिए भी चलता है, बस D पर reflex angle को गिनना है। यहाँ diagonal BD अंदर है, और ये "
           "shape को triangles A B D और B C D में बाँटता है। फिर से two triangles, तो three hundred and sixty degrees.",
           ["बस D पर reflex angle को गिनना है", "triangles A B D और B C D में बाँटता है",
            "तो three hundred and sixty degrees"], None),
    "13": ("अब आपकी बारी। A, B और C पर angles twenty-nine, forty और twenty-nine degrees हैं। D पर interior angle "
           "कितना है?",
           ["D पर interior angle कितना है"],
           ("A, B और C के angles 29°, 40°, 29° हैं। D पर interior angle कितना है?", ["262°", "98°", "82°"],
            ["हाँ। 360 में से 98 घटाइए, 262 degrees बचते हैं: एक reflex angle.",
             "98 degrees, dent के बाहर वाला angle है। Interior angle वो है जो अंदर है।",
             "इसमें 180 degrees लिया गया है, जो triangle का sum है। Quadrilateral के angles का sum 360 है।"])),
    "14": ("Three hundred and sixty में से ninety-eight घटाइए, तो two hundred and sixty-two degrees बचते हैं। ये one "
           "hundred and eighty से ज़्यादा है, तो D पर angle reflex है, और shape concave है।",
           ["Three hundred and sixty में से", "shape concave है"], None),
    "15": ("तो, short में। Convex quadrilateral का हर interior angle one hundred and eighty degrees से कम होता है, और "
           "उसके diagonals अंदर cross करते हैं। Concave में उसके dent पर एक reflex angle होता है। एक से दूसरे में जाते "
           "हुए, shape एक पल के लिए दब जाती है। और चारों interior angles का sum हमेशा three hundred and sixty "
           "degrees होता है।",
           ["हर interior angle one hundred and eighty degrees से कम", "Concave में उसके dent पर एक reflex angle",
            "shape एक पल के लिए दब जाती है", "हमेशा three hundred and sixty degrees होता है"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 3 (Hindi): convex and concave")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u3_hi.json")
