"""Unit 5 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit5 import L

T = {
    "01": ("इस lesson का हर proof two tools इस्तेमाल करता है। ये रहीं two parallel lines, और उन्हें काटती एक तीसरी line. "
           "Parallels के बीच, काटने वाली line के दोनों ओर बनने वाले angles को alternate angles कहते हैं। ये Z shape "
           "बनाते हैं, और ये equal होते हैं।",
           ["ये रहीं two parallel lines", "alternate angles कहते हैं", "ये equal होते हैं"], None),
    "02": ("अब काटने वाली line के एक ही ओर, parallels के बीच के two angles लीजिए। ये same-side interior angles जुड़कर "
           "one hundred and eighty degrees बनाते हैं।",
           ["ये same-side interior angles", "one hundred and eighty degrees बनाते हैं"], None),
    "03": ("खुद check कीजिए। एक same-side interior angle seventy degrees है। दूसरा कितना है?",
           ["दूसरा कितना है"],
           ("एक same-side interior angle 70° है। दूसरा कितना है?", ["110°", "70°", "290°"],
            ["हाँ। Same-side interior angles का sum 180° है, और 180 − 70 = 110.",
             "equal तो ALTERNATE angles होते हैं। Same-side interior angles का sum 180° होता है।",
             "तब दोनों का sum 360° हो जाएगा। Parallels के बीच इनका sum 180° है।"])),
    "04": ("ये one hundred and ten degrees है, क्योंकि seventy और one hundred and ten मिलकर one hundred and eighty बनते "
           "हैं। हमारा दूसरा tool है congruent triangles: जब two triangles congruent हों, तो उनकी सारी matching sides और "
           "angles equal होते हैं।",
           ["ये one hundred and ten degrees है", "हमारा दूसरा tool है congruent triangles"], None),
    "05": ("एक parallelogram से शुरू कीजिए: AB, DC के parallel है, और AD, BC के parallel है। Diagonal AC खींचिए। "
           "क्योंकि AB, DC के parallel है, angle B A C equal है angle D C A के: ये alternate angles हैं।",
           ["एक parallelogram से शुरू कीजिए", "Diagonal AC खींचिए", "angle B A C equal है angle D C A के"], None),
    "06": ("क्योंकि AD, BC के parallel है, angle B C A equal है angle D A C के, फिर से alternate angles. अब triangles "
           "A B C और C D A कौन सा congruence test पूरा करते हैं?",
           ["angle B C A equal है angle D A C के", "कौन सा congruence test"],
           ("Triangles ABC और CDA कौन सा congruence test पूरा करते हैं?", ["ASA", "SSS", "SAS"],
            ["हाँ। equal angles के two pairs, और उनके बीच की side AC, जो दोनों में common है।",
             "SSS को equal sides के three pairs चाहिए, और equal sides ही तो हम साबित करना चाहते हैं।",
             "SAS को equal sides के two pairs चाहिए। हमें सिर्फ़ एक पता है: AC, जो common है।"])),
    "07": ("ASA: two angles, और उनके बीच की side AC, जो दोनों triangles में common है। तो triangles congruent हैं, और "
           "उनकी matching sides equal हैं: AB equal है CD के, और BC equal है DA के।",
           ["ASA", "AB equal है CD के, और BC equal है DA के"], None),
    "08": ("अब angles. Angle A और angle B, parallel sides AD और BC के बीच हैं, AB के एक ही ओर। तो angle A plus angle B, "
           "one hundred and eighty degrees है। इसी तरह, angle B plus angle C भी one hundred and eighty degrees है। "
           "इससे क्या निकलता है?",
           ["angle A plus angle B, one hundred and eighty degrees है", "angle B plus angle C भी",
            "इससे क्या निकलता है"],
           ("∠A + ∠B = 180° और ∠B + ∠C = 180°. इससे क्या निकलता है?", ["∠A = ∠C", "∠A = ∠B", "∠B = 90°"],
            ["हाँ। दोनों sum 180° हैं और दोनों में ∠B है, तो जो बचता है वो equal होगा।",
             "∠A और ∠B का sum 180° है। ये तभी equal होंगे जब दोनों 90° हों।",
             "कहीं नहीं कहा कि angles right angles हैं। देखिए दोनों जोड़ों में common क्या है।"])),
    "09": ("Angle A equal है angle C के। दोनों sum one hundred and eighty हैं, और दोनों में angle B है। हर एक में से "
           "angle B हटा दीजिए, जो बचता है वो equal है। इसी तरह, angle B equal है angle D के।",
           ["Angle A equal है angle C के", "angle B हटा दीजिए", "angle B equal है angle D के"], None),
    "10": ("आखिरी theorem. Diagonals E पर मिलते हैं। हमने chapter two में साबित किया था कि AB equal है CD के, तो अब उसे "
           "इस्तेमाल कर सकते हैं। Alternate angles से angle B A E equal है angle D C E के, और angle A B E equal है "
           "angle C D E के।",
           ["हमने chapter two में साबित किया था कि AB equal है CD के", "angle B A E equal है angle D C E के",
            "angle A B E equal है angle C D E के"], None),
    "11": ("तो triangles A B E और C D E, ASA से congruent हैं। उनकी matching sides equal हैं: AE equal है CE के, और BE "
           "equal है DE के। E दोनों diagonals का midpoint है: वो एक-दूसरे को bisect करते हैं। क्रम पर ध्यान दीजिए। हमने "
           "सिर्फ़ पहले साबित किए facts इस्तेमाल किए। Result से ही result को साबित करना circular होता।",
           ["ASA से congruent हैं", "AE equal है CE के, और BE equal है DE के", "सिर्फ़ पहले साबित किए facts"], None),
    "12": ("Converse में if और then की जगह बदल जाती है। Theorem: अगर A B C D एक parallelogram है, तो उसकी opposite sides "
           "equal हैं। Converse: अगर opposite sides equal हैं, तो A B C D एक parallelogram है। ये converse सच है। हमने "
           "इसे पिछले lesson में test two के रूप में साबित किया था।",
           ["Converse में if और then की जगह बदल जाती है", "Converse: अगर opposite sides equal हैं",
            "ये converse सच है"], None),
    "13": ("पर कोई converse सिर्फ़ इसलिए सच नहीं होता कि original सच है। एक सच्चा statement: अगर कोई quadrilateral "
           "square है, तो उसकी चारों sides equal हैं। अब converse: अगर किसी quadrilateral की चारों sides equal हों, तो "
           "क्या वो square ही होगा?",
           ["अगर कोई quadrilateral square है", "क्या वो square ही होगा"],
           ("अगर किसी quadrilateral की चारों sides equal हों, तो क्या वो square ही होगा?", ["नहीं", "हाँ"],
            ["सही। Rhombus की चारों sides equal होती हैं, पर right angles नहीं होते।",
             "एक counterexample ढूँढिए: square को तिरछा कीजिए, sides की लंबाई वही रखिए।"])),
    "14": ("नहीं। इस rhombus की चारों sides equal हैं, पर इसके angles right angles नहीं हैं। Converse को गलत दिखाने के "
           "लिए एक counterexample काफ़ी है। तो हर converse को test कीजिए: या तो साबित कीजिए, या counterexample "
           "ढूँढिए।",
           ["इस rhombus की चारों sides equal हैं", "इसके angles right angles नहीं हैं",
            "या तो साबित कीजिए, या counterexample ढूँढिए"], None),
    "15": ("तो, parallelogram में opposite sides equal होती हैं, diagonal पर ASA से। Opposite angles equal होते हैं, "
           "क्योंकि same-side angles का sum one hundred and eighty है। और diagonals एक-दूसरे को bisect करते हैं, उन "
           "equal sides से जो हमने पहले साबित कीं। हर proof सिर्फ़ अपने से पहले वालों पर टिका है।",
           ["opposite sides equal होती हैं", "Opposite angles equal होते हैं", "diagonals एक-दूसरे को bisect करते हैं",
            "हर proof सिर्फ़ अपने से पहले वालों पर टिका है"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 5 (Hindi): proving the parallelogram theorems")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u5_hi.json")
