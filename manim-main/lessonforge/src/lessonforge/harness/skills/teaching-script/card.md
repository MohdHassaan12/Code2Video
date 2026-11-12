# Filling the teaching card

The card is one page that says how THIS topic is taught. It is adapted from the CoRe
form that Loughran, Mulhall and Berry (2004) use to write down what an experienced
teacher knows about teaching one idea. You fill it from the numbered passages you are
given.

## How to read the sources

- **The textbook chapter** decides what must be taught, the words and notation the
  class uses, and what the class has met before. When the chapter gives the reason a
  rule is true, that reason is the card's WHY.
- **The lectures** show how good teachers actually walk through it: what they open
  with, which example and picture they use, where they slow down, what they ask. Where
  two or three lectures take the same route, that route is probably the topic's own.
  Where one does something the others do not (a better opening, a clearer picture),
  consider taking it. Do NOT average them: three ordinary explanations averaged make
  an ordinary one. Choose.
- **A lesson plan or a list of mistakes** says where learners go wrong. Use its
  mistakes as they are documented. They become the wrong choices in questions.
- **Activities** in the textbook or the lesson plan are candidates for the try-it task.
- **The plans** (under HOW EACH SOURCE TEACHES IT, when given) are each source's lesson
  plan, worked out from the source: what it aims at, its phases in order with the role
  each plays (motivation, activation, demonstration, application, integration,
  assessment), how its examples progress, what it leaves out, and how the lecturer
  talks. The passages say WHAT the sources say; the plans say HOW they teach. Lay the
  flows side by side before you write the route: an order two sources share is probably
  the topic's own; a role none of them skips belongs in your route; a role all of them
  skip (often activation, or integration) is a gap you may fill in one move. What a
  source leaves out is a candidate for `leave_out`.

## Rules

1. Every line cites the passages it stands on, by id (`"cites": ["S1#4", "S3#2"]`).
   A line that comes from your own knowledge has an empty list and is also named in
   `uncited`. Never invent a source or an id.
2. Say everything in your own words. The sources may be read and cited, not copied:
   reuse no sentence from a textbook or a lecture.
2a. `objectives`: two to four things the learner can DO after the lesson, each starting
   with a verb and tagged with the level of thinking it takes (Anderson and Krathwohl's
   revision of Bloom): remember (name, state), understand (explain, describe, compare),
   apply (work out, use, predict), analyze (tell apart, relate), evaluate (justify),
   create (design). Tag by what the lesson really makes the learner do. At least one
   is above remember: a lesson that only names things has taught a list. Each says
   where in this card it is done (`checked_by`: opening, q1, q2, q3 or try_it), because
   an objective nothing in the lesson exercises is a wish. Say what is transferable,
   not a restated fact: "explain why a cell needs more than one kind of part", never
   "know that the nucleus controls the cell".
3. `the_why` is a REASON, one or two sentences, in words a picture can show. "Because
   the rule says so" and a restatement of the big idea are not reasons.
4. `picture` is ONE picture that can SHOW the why, simple enough to draw with shapes,
   dots, tiles, arrows, a number line, a graph. Say what it looks like at the start and
   how it changes. No story around it, no people, no festival, no shop.
   Most topics have a STANDARD way of being drawn that every textbook and every
   teacher's board uses: the division ladder for prime factors (the number beside a
   vertical line, each prime divisor on the left, the quotients going down to 1), a
   factor tree, a number line, an area model, a bar model, a place-value table, a
   balance for an equation, a free-body diagram, a ray diagram. When the sources draw
   the topic in such a way, name it in `standard` and build the picture ON it, written
   out exactly (what is on which side, what goes downward, where the answer appears),
   so the lesson looks like the learner's own notebook. Then add what a board cannot
   do: things move. An invented picture (tiles in trays) may follow the standard one
   to show the why; it never replaces it.
   `diagram_ask`: a request to the drawing service for the picture this topic is KNOWN
   BY. Ask for a picture, never for the topic: a topic's name ("inertia") cannot be
   drawn. It is one of three things: the real thing as a labelled diagram ("Labelled
   diagram of an animal cell"); the classic demonstration or everyday situation that
   makes the idea visible, as one still picture with before and after side by side ("A
   coin resting on a card on top of a glass, and beside it the same glass after the
   card is flicked away sideways with the coin fallen straight down into the glass");
   or the standard diagram of the method ("Ray diagram of a convex lens with the object
   between F and 2F", "The division ladder for the prime factors of 36"). Prefer the
   one the textbook passages show or describe: its own activity, its own figure. One
   sentence naming the objects, how they are arranged, three to seven things to label
   and any arrows. A labelled diagram comes back with its parts cut out and the lesson
   lights each as it is named; a demonstration or a standard form is shown whole.
   Leave it empty only when the picture must be built step by step with the lesson's
   own numbers (tiles being dealt into trays, a bar being cut): that is drawn by code.
5. `opening_question` is about the big idea, in the plain numbers or objects of the
   topic and in words the learner already has BEFORE the lesson ("Can 1156 tiles be laid
   as a perfect square?", never "can it be split into two identical groups of prime
   factors?"). A learner of this class can make a guess at it from what they already
   know. Give two or three guesses a learner might make, and the answer.
6. `mistakes`: the two to four that matter most, each with why it fails. Prefer ones a
   source documents.
7. `route` is the order of moves for THIS topic, six to nine of them, each naming what
   is shown and what is asked. It includes two cases side by side where the idea is a
   test (one that passes, one that fails).
8. `questions`: two or three that make the learner predict or decide, never only
   recall a word. The wrong choices are the card's mistakes.
9. `try_it` follows `practicum.md`.
10. `leave_out`: what is true and nearby but not for this lesson.
11. `from_lectures`: for each lecture, one line on what you took and one on what you
    left, so a person can check your choices.
