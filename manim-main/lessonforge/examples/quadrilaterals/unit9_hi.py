"""Unit 9 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit9 import L

T = {
    "01": ("फ़र्श अक्सर square या rectangle वाली tiles से ढका होता है। Rectangle की copies बिना gap और बिना overlap के "
           "आपस में फिट हो जाती हैं। ये रही एक अलग tile, A B C D. इसकी कोई two sides equal नहीं, और कोई two sides "
           "parallel नहीं।",
           ["Rectangle की copies", "ये रही एक अलग tile, A B C D", "इसकी कोई two sides equal नहीं"], None),
    "02": ("पहले अंदाज़ा लगाइए। अगर हम सिर्फ़ इसी tile की copies इस्तेमाल करें, घुमाकर पर कभी काटे बिना, तो क्या वो पूरा "
           "फ़र्श बिना gap के ढक सकती हैं?",
           ["पहले अंदाज़ा लगाइए", "घुमाकर पर कभी काटे बिना", "पूरा फ़र्श बिना gap के ढक सकती हैं"],
           ("क्या इस irregular quadrilateral की copies, फ़र्श को बिना gap या overlap के ढक सकती हैं?",
            ["हाँ, हमेशा", "नहीं, gaps रहेंगे", "सिर्फ़ तब जब कुछ copies काटें"],
            ["यही अंदाज़ा है। अब फ़र्श बनाकर देखते हैं कि क्यों।",
             "बहुत लोग यही सोचते हैं, क्योंकि tile irregular है। तय करने से पहले construction देखिए।",
             "काटने की ज़रूरत नहीं। देखिए half turn क्या करता है।"])),
    "03": ("Side BC का midpoint M mark कीजिए। अब tile की एक copy लीजिए और उसे M के चारों ओर half turn दीजिए, one hundred and "
           "eighty degrees.",
           ["Side BC का midpoint M mark कीजिए", "half turn दीजिए", "one hundred and eighty degrees"], None),
    "04": ("देखिए copy कहाँ आती है। B और C की जगह आपस में बदल जाती है, तो copy की side ठीक BC पर आ जाती है। लंबाई वही है, "
           "तो दोनों tiles वो side share करती हैं, बिना gap और बिना overlap के।",
           ["B और C की जगह आपस में बदल जाती है", "copy की side ठीक BC पर आ जाती है", "बिना gap और बिना overlap के"],
           None),
    "05": ("हम ये हर tile की हर side के लिए कर सकते हैं: उस side के midpoint के चारों ओर एक copy घुमाइए। ऐसे करते जाइए, "
           "और copies पूरे फ़र्श पर फैल जाती हैं।",
           ["हर tile की हर side के लिए", "copies पूरे फ़र्श पर फैल जाती हैं"], None),
    "06": ("Sides तो मिल गईं, पर corners का क्या? Point C को देखिए। वहाँ four tiles मिलती हैं। A B C D के कौन से angles "
           "उसके चारों ओर की जगह भरते हैं?",
           ["पर corners का क्या", "वहाँ four tiles मिलती हैं", "A B C D के कौन से angles"],
           ("Point C पर four tiles मिलती हैं। ABCD के कौन से angles उसके चारों ओर हैं?",
            ["हर एक का एक: A, B, C और D", "angle C की four copies", "two C और two A"],
            ["हाँ। हर tile एक अलग corner लाती है, तो A, B, C और D हर एक बार आते हैं।",
             "चारों tiles फिर से देखिए: हर एक, C को अलग corner से छूती है।",
             "Corners फिर से गिनिए: हर tile, C को अलग corner से छूती है।"])),
    "07": ("हर एक का एक। A B C D के चारों angles C पर मिलते हैं, और किसी भी quadrilateral के चारों angles का sum three "
           "hundred and sixty degrees होता है। ये ठीक एक पूरा चक्कर है, तो corners बिना gap के बंद हो जाते हैं।",
           ["चारों angles C पर मिलते हैं", "three hundred and sixty degrees होता है", "ठीक एक पूरा चक्कर है",
            "बिना gap के बंद हो जाते हैं"], None),
    "08": ("Numbers के साथ करके देखिए। एक point पर मिलने वाले three angles seventy, ninety-five और one hundred and ten "
           "degrees हैं। चौथा angle कितना होना चाहिए?",
           ["seventy, ninety-five और one hundred and ten", "चौथा angle कितना होना चाहिए"],
           ("Tiling के एक point पर three angles 70°, 95° और 110° हैं। चौथा कितना है?", ["85°", "95°", "180°"],
            ["हाँ। 70 + 95 + 110 = 275, और 360 − 275 = 85°.",
             "चौथा corner, tile का एक अलग angle है। पूरा चक्कर इस्तेमाल कीजिए: 360 में से तीनों घटाइए।",
             "180° एक सीधी line है। एक point के चारों ओर angles पूरा चक्कर बनाते हैं, 360°."])),
    "09": ("Eighty-five degrees. Seventy plus ninety-five plus one hundred and ten, two hundred and seventy-five, और three "
           "hundred and sixty में से two hundred and seventy-five घटाइए, तो eighty-five.",
           ["two hundred and seventy-five, और", "तो eighty-five"], None),
    "10": ("ये concave tile के लिए भी चलता है, जैसे ये arrowhead shape. Side midpoints के चारों ओर half turns अब भी फिट "
           "होते हैं, क्योंकि इसके चारों angles का sum अब भी three hundred and sixty degrees है।",
           ["concave tile के लिए भी", "half turns अब भी फिट होते हैं", "चारों angles का sum अब भी three hundred and sixty"],
           None),
    "11": ("एक सीमा है। Tile एक सच्चा quadrilateral होनी चाहिए, यानी उसकी sides cross नहीं होनी चाहिए। Crossed shape "
           "quadrilateral नहीं है, और वो इस तरह tile नहीं कर सकती।",
           ["उसकी sides cross नहीं होनी चाहिए", "Crossed shape quadrilateral नहीं है"], None),
    "12": ("तो, कोई भी quadrilateral फ़र्श को tile कर सकता है। एक copy को side के midpoint के चारों ओर half turn दीजिए, और "
           "sides मिल जाती हैं। हर corner पर चारों angles मिलते हैं, हर एक का एक, और क्योंकि उनका sum three hundred "
           "and sixty degrees है, वो बिना gap के बंद हो जाते हैं।",
           ["कोई भी quadrilateral फ़र्श को tile कर सकता है", "side के midpoint के चारों ओर",
            "चारों angles मिलते हैं, हर एक का एक", "उनका sum three hundred and sixty degrees है"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 9 (Hindi): tiling the plane with any quadrilateral")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u9_hi.json")
