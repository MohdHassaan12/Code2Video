"""Unit 6 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit6 import L

T = {
    "01": ("ये रहा triangle A B C. P, side AB का midpoint है, तो AP equal है PB के। Q, side AC का midpoint है, तो AQ "
           "equal है QC के। अब P को Q से जोड़िए।",
           ["P, side AB का midpoint है", "Q, side AC का midpoint है", "अब P को Q से जोड़िए"], None),
    "02": ("कुछ भी नापने से पहले, अंदाज़ा लगाइए। आपको क्या लगता है, PQ तीसरी side BC से कैसे मिलती है?",
           ["अंदाज़ा लगाइए", "PQ तीसरी side BC से कैसे मिलती है"],
           ("P और Q, AB और AC के midpoints हैं। PQ और BC के बारे में आपका अंदाज़ा क्या है?",
            ["PQ ∥ BC, और PQ, BC का half", "PQ ∥ BC, और PQ = BC", "कोई संबंध नहीं"],
            ["यही अंदाज़ा हम अब test करेंगे, फिर साबित करेंगे।",
             "PQ parallel दिखती है, पर लंबाई देखिए: PQ सिर्फ़ half रास्ते तक पहुँचती है।",
             "संबंध है। PQ की दिशा देखिए, और वो कितनी दूर तक जाती है।"])),
    "03": ("PQ, BC के parallel दिखती है, और half लंबी दिखती है। पर drawing आँखों को धोखा दे सकती है। Proof किसे "
           "माना जाएगा?",
           ["PQ, BC के parallel दिखती है", "drawing आँखों को धोखा दे सकती है", "Proof किसे माना जाएगा"],
           ("किस चीज़ को proof माना जाएगा कि PQ ∥ BC और PQ = ½ BC?",
            ["ऐसा तर्क जो हर triangle पर चले", "इसी drawing को ध्यान से नापना", "three अलग drawings check करना"],
            ["हाँ। Proof सिर्फ़ conditions इस्तेमाल करता है, तो वो हर triangle पर लागू होता है, सिर्फ़ इस पर नहीं।",
             "नापना एक drawing दिखाता है, और उतना ही सही जितना ruler. ये evidence है, proof नहीं।",
             "three examples फिर भी examples ही हैं। चौथा triangle pattern तोड़ सकता है।"])),
    "04": ("ये है midpoint theorem. Conditions: P, AB का midpoint है, और Q, AC का midpoint है। Conclusion: PQ, BC के "
           "parallel है, और PQ, BC का half है। यहाँ BC six centimetres है, तो PQ three centimetres है।",
           ["Conditions", "PQ, BC के parallel है", "PQ, BC का half है", "तो PQ three centimetres है"], None),
    "05": ("एक नया triangle लीजिए। यहाँ भी P और Q, AB और AC के midpoints हैं, और BC nine centimetres है। PQ कितनी लंबी "
           "है?",
           ["यहाँ भी P और Q, AB और AC के midpoints हैं", "BC nine centimetres है", "PQ कितनी लंबी है"],
           ("P और Q, AB और AC के midpoints हैं, और BC = 9 cm. PQ कितनी लंबी है?", ["4.5 cm", "9 cm", "18 cm"],
            ["हाँ। PQ = ½ × 9 = 4.5 cm.",
             "PQ, BC के parallel है, पर उसके equal नहीं। ये midpoints को जोड़ती है, तो half है।",
             "ये BC का दोगुना है। PQ छोटी है: BC का half।"])),
    "06": ("पहले conditions check कीजिए: P और Q दोनों midpoints हैं, तो theorem लागू होता है। फिर PQ, nine का half है, "
           "यानी four point five centimetres.",
           ["पहले conditions check कीजिए", "फिर PQ, nine का half है"], None),
    "07": ("अब proof. हम एक extra point बनाएँगे, और हर कदम क्यों सही है, ये बताएँगे। PQ को Q के आगे एक point R तक बढ़ाइए, "
           "ताकि QR equal हो PQ के। फिर C को R से जोड़िए।",
           ["हर कदम क्यों सही है", "PQ को Q के आगे एक point R तक बढ़ाइए", "फिर C को R से जोड़िए"], None),
    "08": ("Triangles A P Q और C R Q को देखिए। AQ equal है CQ के, क्योंकि Q midpoint है। PQ equal है RQ के, क्योंकि "
           "हमने R ऐसे ही बनाया। और Q पर angles vertically opposite हैं, तो equal हैं। तो triangles SAS से congruent "
           "हैं।",
           ["AQ equal है CQ के", "PQ equal है RQ के", "vertically opposite", "SAS से congruent"], None),
    "09": ("तो CR equal है AP के, और AP equal है PB के, तो CR equal है PB के। साथ ही angle P A Q equal है angle R C Q "
           "के। इससे CR, AB के parallel क्यों हो जाती है?",
           ["तो CR equal है PB के", "angle P A Q equal है angle R C Q के", "इससे CR, AB के parallel क्यों हो जाती है"],
           ("∠PAQ = ∠RCQ. इससे CR, AB के parallel क्यों होती है?",
            ["ये line AC पर equal alternate angles हैं", "CR, AB के parallel दिखती है", "CR = PB"],
            ["हाँ। AC, AB और CR दोनों को काटती है, और equal alternate angles का मतलब है lines parallel हैं।",
             "दिखना कोई वजह नहीं है। Angle वाला fact बताइए।",
             "equal लंबाई से दिशा का कुछ पता नहीं चलता। AC पर two equal angles देखिए।"])),
    "10": ("ये line AC पर equal alternate angles हैं, तो CR, AB के parallel है। अब P B C R को देखिए। इसकी sides PB और CR "
           "equal भी हैं और parallel भी, तो test five से ये parallelogram है। तो PR, BC के parallel है, और PR equal है "
           "BC के। PQ, PR का half है, तो PQ, BC का half है।",
           ["तो CR, AB के parallel है", "तो test five से ये parallelogram है",
            "तो PR, BC के parallel है, और PR equal है BC के", "तो PQ, BC का half है"], None),
    "11": ("अब converse. एक side के midpoint से शुरू कीजिए, और दूसरी side के parallel एक line खींचिए। तब वो तीसरी side "
           "को उसके midpoint पर काटती है। देखिए P, AB पर खिसकता है, और PQ, BC के parallel रहती है। AP से PB, और AQ से "
           "QC, साथ-साथ बदलते हैं। जब P midpoint पर पहुँचता है, Q भी पहुँच जाता है।",
           ["अब converse", "देखिए P, AB पर खिसकता है", "साथ-साथ बदलते हैं", "जब P midpoint पर पहुँचता है"], None),
    "12": ("दोनों conditions ज़रूरी हैं। बाईं ओर PQ midpoint से शुरू होती है, पर parallel नहीं है, और Q midpoint से चूक "
           "जाता है। दाईं ओर PQ parallel है, पर midpoint से शुरू नहीं होती, और Q फिर चूक जाता है।",
           ["दोनों conditions ज़रूरी हैं", "पर parallel नहीं है", "पर midpoint से शुरू नहीं होती"], None),
    "13": ("अब example. Triangle D E F में G, DE का midpoint है, और GH, EF के parallel है। DH four centimetres है, और GH "
           "five centimetres. DF कितनी लंबी है?",
           ["G, DE का midpoint है", "GH, EF के parallel है", "DH four centimetres है", "DF कितनी लंबी है"],
           ("G, DE का midpoint है, GH ∥ EF, DH = 4 cm. DF कितनी लंबी है?", ["8 cm", "4 cm", "10 cm"],
            ["हाँ। Converse से H, DF का midpoint है, तो DF = 2 × 4 = 8 cm.",
             "4 cm तो DH है, DF का सिर्फ़ half। Converse से H, DF का midpoint है।",
             "10 cm, EF है, एक अलग side. DF पर converse लगाइए: H उसका midpoint है।"])),
    "14": ("Converse से H, DF का midpoint है, तो DF, DH का दोगुना है: eight centimetres. अब H भी midpoint है। तो EF कितनी "
           "है?",
           ["H, DF का midpoint है", "eight centimetres", "तो EF कितनी है"],
           ("G और H, DE और DF के midpoints हैं, और GH = 5 cm. EF कितनी लंबी है?", ["10 cm", "5 cm", "2.5 cm"],
            ["हाँ। Midpoint theorem से GH = ½ EF, तो EF = 2 × 5 = 10 cm.",
             "GH, EF के parallel है, equal नहीं। GH, EF का half है।",
             "ये GH का half है। EF बड़ी side है: GH उसका half है।"])),
    "15": ("Midpoint theorem से GH, EF का half है, तो EF ten centimetres है। two कदम, two वजहें: converse ने midpoint दिया, "
           "और theorem ने लंबाई।",
           ["तो EF ten centimetres है", "converse ने midpoint दिया", "theorem ने लंबाई"], None),
    "16": ("तो, midpoint theorem: two sides के midpoints जोड़िए, तो आपको तीसरी side के parallel और उसकी half लंबाई का "
           "segment मिलता है। हमने इसे एक parallelogram बनाकर साबित किया। और converse: एक midpoint से, दूसरी side के "
           "parallel line, तीसरी side को उसके midpoint पर काटती है।",
           ["two sides के midpoints जोड़िए", "तीसरी side के parallel और उसकी half लंबाई", "एक parallelogram बनाकर साबित किया",
            "और converse"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 6 (Hindi): the midpoint theorem")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u6_hi.json")
