"""Unit 4 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English.
Names of three or more letters are spoken letter by letter ("triangle A B C"): the Hindi voice read "ABCD" as a word."""
import sys
from common import in_hindi, write_hi
from unit4 import L

T = {
    "01": ("Parallelogram एक ऐसा quadrilateral है जिसमें opposite sides के दोनों pairs parallel होते हैं। यहाँ AB, DC के "
           "parallel है, और AD, BC के parallel है। Arrow के निशान बताते हैं कि कौन सी sides parallel हैं: पहले pair पर "
           "एक arrow, दूसरे पर दो।",
           ["opposite sides के दोनों pairs parallel होते हैं", "AB, DC के parallel है", "AD, BC के parallel है",
            "Arrow के निशान बताते हैं"], None),
    "02": ("ये वाक्य definition है। ये बताता है कि parallelogram क्या है। पर parallel lines को check करना हमेशा आसान "
           "नहीं होता। इसलिए हम tests भी इस्तेमाल करते हैं। Test एक अलग fact है, जो सच हो जाए, तो साबित कर देता है कि "
           "shape parallelogram ही है।",
           ["ये वाक्य definition है", "इसलिए हम tests भी इस्तेमाल करते हैं"], None),
    "03": ("जल्दी से check करते हैं। इनमें से parallelogram की definition कौन सी है?",
           ["इनमें से parallelogram की definition कौन सी है"],
           ("Parallelogram की definition कौन सी है?",
            ["opposite sides के दोनों pairs parallel", "opposite sides के दोनों pairs equal",
             "diagonals एक-दूसरे को bisect करते हैं"],
            ["हाँ। Definition बताती है कि shape क्या है: opposite sides parallel, दोनों pairs.",
             "ये हर parallelogram में सच है, पर ये एक test है, definition नहीं।",
             "ये भी हर parallelogram में सच है, पर ये एक test है, जो definition से साबित होता है।"])),
    "04": ("जवाब है पहला। अब five tests. कोई quadrilateral parallelogram है अगर इनमें से कोई एक भी सच हो। Test one "
           "खुद definition है: opposite sides के दोनों pairs parallel हैं।",
           ["अब five tests", "Test one खुद definition है"], None),
    "05": ("Test two: opposite sides के दोनों pairs equal हैं। AB equal है CD के, और AD equal है BC के। पहले pair पर एक "
           "tick, दूसरे पर two ticks.",
           ["opposite sides के दोनों pairs equal हैं", "AB equal है CD के, और AD equal है BC के"], None),
    "06": ("Test three: opposite angles के दोनों pairs equal हैं। Angle A equal है angle C के, और angle B equal है "
           "angle D के।",
           ["opposite angles के दोनों pairs equal हैं", "Angle A equal है angle C के"], None),
    "07": ("Test four: diagonals एक-दूसरे को bisect करते हैं। वो E पर cross करते हैं, और E दोनों का midpoint है। AE "
           "equal है EC के, और BE equal है ED के।",
           ["diagonals एक-दूसरे को bisect करते हैं", "E दोनों का midpoint है", "AE equal है EC के, और BE equal है ED के"],
           None),
    "08": ("Test five: opposite sides का एक pair equal भी है और parallel भी। यहाँ AB equal है DC के, और AB, DC के "
           "parallel है। equal और parallel, दोनों एक ही pair होना चाहिए।",
           ["opposite sides का एक pair equal भी है और parallel भी", "दोनों एक ही pair होना चाहिए"], None),
    "09": ("अब एक जाल। इस kite में equal sides के two pairs हैं। क्या ये parallelogram है?",
           ["इस kite में equal sides के two pairs हैं", "क्या ये parallelogram है"],
           ("इस kite में equal sides के two pairs हैं। क्या ये parallelogram है?", ["नहीं", "हाँ"],
            ["सही। इसकी equal sides एक-दूसरे के बगल में हैं, आमने-सामने नहीं।",
             "देखिए equal sides कहाँ हैं: AB और AD, A पर मिलती हैं, तो वो adjacent हैं, opposite नहीं।"])),
    "10": ("नहीं। Kite में AB equal है AD के, पर ये दोनों sides A पर मिलती हैं। ये adjacent हैं, opposite नहीं। Test two "
           "के लिए opposite sides equal होनी चाहिए।",
           ["ये दोनों sides A पर मिलती हैं", "Test two के लिए opposite sides equal होनी चाहिए"], None),
    "11": ("एक और जाल। इस shape में AB, DC के parallel है, और AD equal है BC के। क्या ये parallelogram है?",
           ["AB, DC के parallel है, और AD equal है BC के", "क्या ये parallelogram है"],
           ("AB, DC के parallel है और AD equal है BC के। क्या ये parallelogram है?", ["नहीं", "हाँ"],
            ["सही। Parallel pair और equal pair, अलग-अलग pairs हैं।",
             "Test five को एक ही pair चाहिए जो equal भी हो और parallel भी। यहाँ parallel pair, equal pair नहीं है।"])),
    "12": ("नहीं। AB और DC parallel pair हैं, पर AD और BC equal pair हैं। ये अलग-अलग pairs हैं, तो test five लागू नहीं "
           "होता। ये shape एक isosceles trapezium है। Test five के लिए हमें AB को DC के equal भी चाहिए।",
           ["ये अलग-अलग pairs हैं", "ये shape एक isosceles trapezium है", "हमें AB को DC के equal भी चाहिए"], None),
    "13": ("अब test two को साबित करते हैं। हमें दिया है कि AB equal है CD के, और AD equal है BC के। Diagonal AC "
           "खींचिए। ये shape को triangle A B C और triangle C D A में बाँटता है। निशान हमें कौन सा congruence test "
           "देते हैं?",
           ["हमें दिया है कि AB equal है CD के", "Diagonal AC खींचिए", "कौन सा congruence test"],
           ("Triangles ABC और CDA: निशान कौन सा congruence test देते हैं?", ["SSS", "ASA", "SAS"],
            ["हाँ। Sides के three pairs: AB = CD, BC = DA, और AC दोनों में common है।",
             "ASA के लिए two equal angles चाहिए। हमें अभी कोई equal angle नहीं पता: कुछ भी parallel साबित नहीं हुआ।",
             "SAS के लिए sides के बीच का एक equal angle चाहिए। हमें कोई angle दिया ही नहीं गया।"])),
    "14": ("जवाब है SSS. AB equal है CD के, BC equal है DA के, और AC दोनों triangles में common है। तो triangle A B C, "
           "triangle C D A के congruent है।",
           ["जवाब है SSS", "AC दोनों triangles में common है", "तो triangle A B C, triangle C D A के congruent है"],
           None),
    "15": ("Congruent triangles के matching angles equal होते हैं। तो angle B A C equal है angle D C A के। ये line AC पर "
           "alternate angles हैं, और equal alternate angles का मतलब है AB, DC के parallel है। इसी तरह, angle B C A "
           "equal है angle D A C के, तो BC, AD के parallel है। Opposite sides के दोनों pairs parallel हैं। A B C D एक "
           "parallelogram है।",
           ["तो angle B A C equal है angle D C A के", "AB, DC के parallel है", "तो BC, AD के parallel है",
            "A B C D एक parallelogram है"], None),
    "16": ("अब, test four. Diagonals E पर मिलते हैं, और हमें दिया है कि AE equal है CE के, और BE equal है DE के। "
           "Triangles A E B और C E D को देखिए। Angle A E B, angle C E D के equal क्यों है?",
           ["हमें दिया है कि AE equal है CE के", "Triangles A E B और C E D को देखिए",
            "Angle A E B, angle C E D के equal क्यों है"],
           ("Angle AEB, angle CED के equal क्यों है?",
            ["vertically opposite angles", "alternate angles", "triangles congruent हैं"],
            ["हाँ। E पर two सीधी lines cross करती हैं, और वहाँ आमने-सामने के angles equal होते हैं।",
             "Alternate angles के लिए parallel lines चाहिए, और अभी कुछ भी parallel साबित नहीं हुआ।",
             "यही तो हम साबित करना चाहते हैं। इसे खुद को साबित करने के लिए इस्तेमाल नहीं कर सकते।"])),
    "17": ("ये vertically opposite हैं: E पर two सीधी lines cross करती हैं। तो हमारे पास two sides और उनके बीच का angle "
           "है। AE equal है CE के, BE equal है DE के, और E पर angles equal हैं। SAS से, triangle A E B, triangle "
           "C E D के congruent है।",
           ["ये vertically opposite हैं", "two sides और उनके बीच का angle", "SAS से"], None),
    "18": ("तो इनके matching angles equal हैं: angle B A E equal है angle D C E के। ये AC पर alternate angles हैं, तो "
           "AB, CD के parallel है। Triangles A E D और C E B से इसी तरह AD, BC के parallel आता है। A B C D एक "
           "parallelogram है।",
           ["angle B A E equal है angle D C E के", "तो AB, CD के parallel है", "A B C D एक parallelogram है"], None),
    "19": ("आखिर में, test five. AB, DC के parallel है, और AB equal है DC के। दोनों diagonals खींचिए, जो E पर मिलते "
           "हैं। क्योंकि AB, DC के parallel है, AC पर alternate angles equal हैं: angle B A E equal है angle D C E "
           "के। BD पर, angle A B E equal है angle C D E के।",
           ["AB, DC के parallel है, और AB equal है DC के", "दोनों diagonals खींचिए",
            "angle B A E equal है angle D C E के", "angle A B E equal है angle C D E के"], None),
    "20": ("two angles और उनके बीच की side: triangles A B E और C D E, ASA से congruent हैं। तो AE equal है CE के, और BE "
           "equal है DE के। Diagonals एक-दूसरे को bisect करते हैं, और test four से, A B C D एक parallelogram है।",
           ["ASA से congruent हैं", "तो AE equal है CE के", "test four से"], None),
    "21": ("जो सीखा, उसे इस्तेमाल करते हैं। एक quadrilateral में AB equal है CD के, और AB, CD के parallel है। कौन सा "
           "test साबित करता है कि ये parallelogram है?",
           ["कौन सा test साबित करता है"],
           ("AB = CD और AB ∥ CD. कौन सा test साबित करता है कि ABCD एक parallelogram है?",
            ["test five", "test two", "जानकारी काफ़ी नहीं"],
            ["हाँ। Opposite sides का एक pair equal भी है और parallel भी।",
             "Test two को opposite sides के दोनों pairs equal चाहिए। हमें सिर्फ़ AB और CD का पता है।",
             "काफ़ी है: test five को सिर्फ़ एक pair चाहिए, बस वो equal भी हो और parallel भी।"])),
    "22": ("Test five. AB और CD, opposite sides का एक pair हैं, और वही pair equal भी है और parallel भी। तो, definition "
           "कहती है कि opposite sides के दोनों pairs parallel हैं। पाँचों tests इसे साबित करने के दूसरे तरीके हैं: sides "
           "के दोनों pairs equal, angles के दोनों pairs equal, diagonals जो एक-दूसरे को bisect करें, या एक pair जो "
           "equal भी हो और parallel भी।",
           ["वही pair equal भी है और parallel भी", "पाँचों tests इसे साबित करने के दूसरे तरीके हैं",
            "sides के दोनों pairs equal"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 4 (Hindi): parallelograms and their tests")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u4_hi.json")
