"""Unit 8 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit8 import L

T = {
    "01": ("ये रहा एक quadrilateral A B C D, जिसकी कोई भी sides equal नहीं, और कोई भी sides parallel नहीं। हर side का "
           "midpoint mark कीजिए: AB पर P, BC पर Q, CD पर R, और DA पर S. अब इन्हें क्रम से जोड़िए, P से Q, Q से R, R से S.",
           ["कोई भी sides parallel नहीं", "हर side का midpoint mark कीजिए", "अब इन्हें क्रम से जोड़िए"], None),
    "02": ("A B C D में कुछ भी ख़ास नहीं है। आपको क्या लगता है, P Q R S किस तरह की shape है?",
           ["कुछ भी ख़ास नहीं है", "P Q R S किस तरह की shape है"],
           ("P, Q, R, S, ABCD की sides के midpoints हैं। PQRS किस तरह की shape है?",
            ["Parallelogram", "ABCD पर निर्भर है", "Rectangle"],
            ["यही अंदाज़ा है। अब इसे साबित करते हैं, ताकि पता हो कि ये किस्मत नहीं है।",
             "अच्छा अंदाज़ा, क्योंकि ABCD irregular है। Proof देखिए: वो ABCD की कोई ख़ास बात इस्तेमाल नहीं करता।",
             "यहाँ इसके angles right angles नहीं हैं। Sides देखिए: कौन से pairs parallel दिखते हैं?"])),
    "03": ("Diagonal AC खींचिए। ये A B C D को two triangles में बाँटता है, A B C और A D C. पहले triangle A B C को देखिए। "
           "P, AB का midpoint है और Q, BC का midpoint है।",
           ["Diagonal AC खींचिए", "two triangles में बाँटता है", "पहले triangle A B C को देखिए",
            "Q, BC का midpoint है"], None),
    "04": ("तो unit six के midpoint theorem से, PQ, AC के parallel है, और PQ, AC का half है।",
           ["midpoint theorem से", "PQ, AC के parallel है", "PQ, AC का half है"], None),
    "05": ("अब triangle A D C. S, AD का midpoint है और R, DC का midpoint है। वही theorem बताता है कि SR, AC के parallel "
           "है, और SR भी AC का half है।",
           ["अब triangle A D C", "S, AD का midpoint है", "SR, AC के parallel है", "SR भी AC का half है"], None),
    "06": ("दोनों को साथ रखिए। PQ और SR दोनों AC के parallel हैं, और दोनों AC के half हैं। ये कौन सा parallelogram test "
           "pass करता है?",
           ["PQ और SR दोनों AC के parallel हैं", "दोनों AC के half हैं", "ये कौन सा parallelogram test pass करता है"],
           ("PQ ∥ SR और PQ = SR. PQRS कौन सा parallelogram test pass करता है?",
            ["Opposite sides का एक pair equal और parallel", "Opposite sides के दोनों pairs parallel",
             "Diagonals एक-दूसरे को bisect करते हैं"],
            ["हाँ। एक pair, PQ और SR, equal भी है और parallel भी। अकेला यही test काफ़ी है।",
             "सच है, पर अभी तक हमने सिर्फ़ एक pair दिखाया है। अभी वाला test एक pair माँगता है, equal और parallel.",
             "हमने PQRS के diagonals को तो देखा ही नहीं। देखिए हमने PQ और SR के बारे में क्या साबित किया।"])),
    "07": ("Opposite sides का एक pair equal और parallel है, तो P Q R S एक parallelogram है। Check के लिए, दूसरा "
           "diagonal BD दूसरे pair के लिए यही देता है: QR और PS दोनों BD के parallel हैं।",
           ["तो P Q R S एक parallelogram है", "दूसरा diagonal BD", "QR और PS दोनों BD के parallel हैं"], None),
    "08": ("Proof ने A B C D की कोई ख़ास बात इस्तेमाल नहीं की। तो अंदाज़ा लगाइए: अगर हम D को अंदर खींच दें, और A B C D "
           "concave हो जाए, तो क्या P Q R S अब भी parallelogram रहेगा?",
           ["Proof ने A B C D की कोई ख़ास बात इस्तेमाल नहीं की", "concave हो जाए",
            "क्या P Q R S अब भी parallelogram रहेगा"],
           ("अगर ABCD concave हो जाए, तो क्या PQRS अब भी parallelogram रहेगा?",
            ["हाँ, हमेशा", "नहीं, सिर्फ़ convex ABCD में", "सिर्फ़ तब जब ABCD parallelogram हो"],
            ["चलिए देखते हैं कि picture, proof से सहमत है या नहीं।",
             "Proof check कीजिए: उसने two triangles और midpoint theorem इस्तेमाल किए। क्या कहीं ABCD का convex होना चाहिए था?",
             "यहाँ ABCD की कोई sides parallel नहीं हैं, फिर भी PQRS parallelogram है।"])),
    "09": ("D को अंदर जाते, और फिर बाहर आते देखिए। Midpoints हिलते हैं, और P Q R S की shape बदलती है, पर इसकी opposite "
           "sides पूरे समय parallel और equal रहती हैं। P Q R S हमेशा parallelogram है।",
           ["D को अंदर जाते", "P Q R S की shape बदलती है", "opposite sides पूरे समय parallel और equal रहती हैं",
            "P Q R S हमेशा parallelogram है"], None),
    "10": ("अब इसे इस्तेमाल कीजिए। एक quadrilateral में diagonal AC ten centimetres है और diagonal BD eight centimetres. "
           "P Q R S का perimeter कितना है?",
           ["AC ten centimetres है", "BD eight centimetres", "P Q R S का perimeter कितना है"],
           ("AC = 10 cm और BD = 8 cm. PQRS का perimeter कितना है?", ["18 cm", "9 cm", "36 cm"],
            ["हाँ। PQ और SR दोनों AC के half, 5 cm; QR और PS दोनों BD के half, 4 cm. 5 + 5 + 4 + 4 = 18 cm.",
             "इसमें हर pair से सिर्फ़ एक side जोड़ी गई है। PQRS की four sides हैं: two 5 cm की और two 4 cm की।",
             "ये दोगुना है। PQRS की हर side एक diagonal का half है, उसके equal नहीं।"])),
    "11": ("Eighteen centimetres. PQ और SR दोनों ten के half हैं, five centimetres. QR और PS दोनों eight के half हैं, four "
           "centimetres. Five plus five plus four plus four, eighteen: दोनों diagonals का sum।",
           ["PQ और SR दोनों ten के half हैं", "QR और PS दोनों eight के half हैं", "दोनों diagonals का sum"], None),
    "12": ("तो, किसी भी quadrilateral की sides के midpoints को क्रम से जोड़िए, और आपको parallelogram मिलेगा। वजह है "
           "midpoint theorem, two बार: P Q R S की हर side, A B C D के एक diagonal के parallel है, और उसका half है।",
           ["किसी भी quadrilateral की sides के midpoints", "आपको parallelogram मिलेगा", "midpoint theorem, two बार",
            "एक diagonal के parallel है, और उसका half है"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 8 (Hindi): the midpoints of any quadrilateral")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u8_hi.json")
