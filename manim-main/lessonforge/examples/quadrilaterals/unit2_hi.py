"""Unit 2 in Hindi: the English lesson's pictures and screen words, Hindi narration with maths words in English."""
import sys
from common import in_hindi, write_hi
from unit2 import L

T = {
    "01": ("क्रम से जुड़े four dots से हमेशा quadrilateral नहीं बनता। three चीज़ें अब भी गलत हो सकती हैं। इसलिए एक "
           "valid quadrilateral को three checks pass करने होते हैं। पहला, चारों points एक ही flat plane पर हों। दूसरा, "
           "shape दब कर एक सीधी line न बन जाए। तीसरा, boundary खुद को कभी cross न करे।",
           ["three चीज़ें अब भी गलत हो सकती हैं", "चारों points एक ही flat plane पर हों", "एक सीधी line न बन जाए",
            "boundary खुद को कभी cross न करे"], None),
    "02": ("ये रहा A B C D, कागज़ की एक sheet पर सपाट रखा हुआ। कुछ भी हिलने से पहले, अंदाज़ा लगाइए। अगर मैं D को "
           "सीधा ऊपर, कागज़ से उठा दूँ, तो कौन सा check fail होगा?",
           ["कागज़ की एक sheet पर सपाट", "तो कौन सा check fail होगा"],
           ("D को कागज़ से उठा दें, तो कौन सा check fail होगा?", ["one flat plane", "no collapse", "no crossing"],
            ["हाँ। A, B और C कागज़ पर रहते हैं और D नहीं, तो चारों points अब एक plane पर नहीं हैं।",
             "कुछ नहीं दबता: कोई three corners एक सीधी line पर नहीं आते।",
             "ऊपर से देखिए: sides एक-दूसरे को नहीं काटतीं।"])),
    "03": ("देखिए। D sheet से ऊपर उठता है। A, B और C अब भी कागज़ पर हैं, पर D नहीं। चारों sides अब भी जुड़ी हैं, फिर "
           "भी वो कोई flat region नहीं घेरतीं। तो ये plane quadrilateral नहीं है। ये पहला check fail करता है।",
           ["D sheet से ऊपर उठता है", "कोई flat region नहीं घेरतीं", "ये पहला check fail करता है"], None),
    "04": ("वापस flat page पर। फिर से अंदाज़ा लगाइए। मैं D को तब तक खिसकाऊँगा जब तक वो ठीक C से A वाली line पर न आ "
           "जाए। उस पल shape का क्या होगा?",
           ["ठीक C से A वाली line पर"],
           ("जब D, C से A वाली line पर आ जाता है, तो क्या होता है?",
            ["ये triangle बन जाता है", "ये quadrilateral ही रहता है", "two sides cross करती हैं"],
            ["हाँ। तब C, D और A एक सीधी line में होते हैं, तो D वाला corner गायब हो जाता है।",
             "असली corners गिनिए: D पर boundary सीधी आगे चली जाती है, तो वहाँ कोई corner नहीं।",
             "कोई side किसी को नहीं काटती; D बस C और A के बीच की line पर है।"])),
    "05": ("देखिए D उस line की ओर खिसकता है। पहुँचने से ठीक पहले, अब भी four corners हैं, और D पर angle लगभग सीधा "
           "angle है। जिस पल D line पर आता है, C, D और A एक सीधी line में हो जाते हैं। D पर angle one hundred and "
           "eighty degrees है, और shape असल में triangle A B C है।",
           ["देखिए D उस line की ओर खिसकता है", "जिस पल D line पर आता है"], None),
    "06": ("इसे degenerate कहते हैं। ये दब गया है। तो दूसरा check ये है: boundary पर लगातार आने वाले कोई three "
           "vertices एक सीधी line पर नहीं होने चाहिए।",
           ["इसे degenerate कहते हैं", "लगातार आने वाले कोई three vertices"], None),
    "07": ("तीसरा check. फिर से A B C D से शुरू कीजिए और D को दाईं ओर ले जाइए। पहले ये shape के अंदर धँसता है और एक "
           "dent बनाता है। फिर ये side BC के पार चला जाता है। अब side DA, side BC को एक ऐसे point पर काटती है जो corner "
           "नहीं है। Boundary खुद को cross करती है।",
           ["D को दाईं ओर ले जाइए", "एक dent बनाता है", "side BC के पार चला जाता है"], None),
    "08": ("यहाँ crossing को mark किया गया है। जो boundary खुद को cross करे, उसे self-intersecting कहते हैं, और वो "
           "quadrilateral नहीं है। यही तीसरा check है।",
           ["उसे self-intersecting कहते हैं", "यही तीसरा check है"], None),
    "09": ("अब आप करके देखिए। इस shape को देखिए। A, B और C नीचे वाले किनारे पर हैं, और D ऊपर है। ये कौन सा check fail "
           "करता है?",
           ["ये कौन सा check fail करता है"],
           ("ये shape कौन सा check fail करती है?", ["no collapse", "no crossing", "one flat plane"],
            ["हाँ। A, B और C एक सीधी line पर हैं, तो B पर कोई corner नहीं है।",
             "Boundary पर चलकर देखिए: कोई side किसी दूसरी को नहीं काटती।",
             "ये flat page पर बनी है, तो चारों points एक ही plane पर हैं।"])),
    "10": ("ये collapse वाला check fail करता है। A, B और C एक सीधी line पर हैं, तो B पर angle one hundred and eighty "
           "degrees है। Shape असल में triangle A C D है।",
           ["ये collapse वाला check fail करता है", "Shape असल में triangle A C D है"], None),
    "11": ("एक पहेली। Triangle A B C से शुरू कीजिए। इसकी sides AB, BC और CA से होकर पूरी lines खींचिए, जो दोनों ओर "
           "हमेशा चलती रहें। ये three lines flat page को seven regions में बाँट देती हैं।",
           ["Triangle A B C से शुरू कीजिए", "पूरी lines खींचिए", "seven regions में बाँट देती हैं"], None),
    "12": ("हमें एक चौथा point D चाहिए, ताकि A B C D एक valid quadrilateral हो, जिसकी sides AB, BC, CD और DA हों। "
           "Test करने से पहले अंदाज़ा लगाइए। seven में से कितने regions में D जा सकता है?",
           ["ताकि A B C D एक valid quadrilateral हो", "seven में से कितने regions में"],
           ("seven में से कितने regions में D जा सकता है?", ["5", "7", "1", "3"],
            ["हाँ। सिर्फ़ two regions fail होते हैं: side AB के पार वाला और side BC के पार वाला।",
             "Side AB के पार वाला region test कीजिए: वहाँ CD, AB को काटती है।",
             "एक से ज़्यादा चलते हैं: triangle के अंदर D रखें तो dent वाली, concave shape बनती है, जो फिर भी valid है।",
             "फिर से गिनिए: corners के पार वाले तीनों regions चलते हैं, और two और भी।"])),
    "13": ("हर region में एक point test करते हैं, boundary पर चलकर: A से B, फिर C, फिर D, और वापस A. हरा tick मतलब "
           "shape हर check pass करती है, लाल cross मतलब fail.",
           ["हर region में एक point test करते हैं", "हरा tick मतलब"], None),
    "14": ("five regions चलते हैं। Triangle के अंदर D एक dent बनाता है, तो A B C D concave है। Side CA के पार ये convex "
           "है। हर corner के पार ये फिर concave है। सिर्फ़ two regions fail होते हैं। Side AB के पार, side CD, AB को काटती "
           "है। Side BC के पार, side DA, BC को काटती है।",
           ["five regions चलते हैं", "सिर्फ़ two regions fail होते हैं"], None),
    "15": ("ये रहीं वो two failures, साथ-साथ। दोनों में boundary खुद को cross करती है। और एक case और: अगर D ठीक इन three "
           "lines में से किसी एक पर हो, तो three vertices एक line में आ जाते हैं, और shape दब जाती है।",
           ["दोनों में boundary खुद को cross करती है", "अगर D ठीक इन three lines में से किसी एक पर हो"], None),
    "16": ("तो, quadrilateral के लिए four dots काफ़ी नहीं। चारों points एक ही flat plane पर हों। लगातार आने वाले कोई "
           "three vertices एक line पर न हों। और boundary खुद को कभी cross न करे। तीनों checks pass कीजिए, और आपके पास "
           "quadrilateral है।",
           ["चारों points एक ही flat plane पर हों", "लगातार आने वाले कोई three vertices एक line पर न हों",
            "boundary खुद को कभी cross न करे", "तीनों checks pass कीजिए"], None),
}

LH = in_hindi(L, T, "Quadrilaterals 2 (Hindi): what makes a shape break")
if __name__ == "__main__":
    write_hi(LH, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u2_hi.json")
