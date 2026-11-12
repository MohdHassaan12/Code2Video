# Narrative storyboard and visualization script

Timings below are measured from synthesized audio; within-sentence action timing is approximate.

## Beat 01 · 00:00–00:25

**Teaching purpose:** Viewer sees two distinct paths: the seven-metre route along two edges versus the unknown diagonal.

**Narration:** Picture a rectangular warehouse floor. A robot starts at the bottom-left corner and needs to reach the top-right corner. It could travel four metres east, then three metres north. That route covers seven metres. But the robot can also drive straight across the diagonal. How long is that shortcut? By the end, you will be able to calculate it and explain why the calculation works.

**Rendered visualization:** Construct the rectangular floor. Move a robot dot east and north along colored legs; reveal the diagonal and the question about its length.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 00:00: Picture a rectangular warehouse floor
- 00:08: It could travel four metres east
- 00:10: then three metres north
- 00:11: That route covers seven metres
- 00:13: But the robot can also drive straight

## Beat 02 · 00:25–00:53

**Teaching purpose:** Viewer identifies the right angle as the corner between the two known legs, not at either end of the diagonal.

**Narration:** Look at those three line segments: the four-metre bottom, the three-metre side, and the diagonal. Together they form a triangle. Where the two legs meet, the corner is a right angle, because the floor is rectangular. The little corner mark tells us it is exactly ninety degrees. Keep watching that mark. It is the condition that makes the relationship we are about to discover possible.

**Rendered visualization:** Remove the floor fill while retaining the three sides. Add and highlight the right-angle marker; name the right triangle.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 00:26: Look at those three line segments
- 00:34: Where the two legs meet
- 00:44: Keep watching that mark

## Beat 03 · 00:53–01:20

**Teaching purpose:** Viewer can state a reasonable range for the diagonal before any formula is applied.

**Narration:** Before calculating, estimate. The diagonal is longer than either leg, so it is more than four metres. But the straight path is shorter than the bent, seven-metre route between the same endpoints. Our answer must lie between four and seven. We do not know it yet, but we already know something useful. An estimate gives us a way to challenge an answer instead of trusting every number a calculation produces.

**Rendered visualization:** Keep the triangle visible. Show 4 < c < 7, highlight the diagonal and compare it with the bent route.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 00:53: Before calculating, estimate
- 00:55: The diagonal is longer than either leg
- 01:00: But the straight path is shorter
- 01:12: An estimate gives us a way

## Beat 04 · 01:20–01:47

**Teaching purpose:** Viewer understands that squaring is not obvious and that the lesson will justify it through area reasoning.

**Narration:** Why would anyone think to square the side lengths? Adding four and three gives seven, the route along the walls. Multiplying gives twelve, but that is not the length of the diagonal either. Squaring has a geometric meaning: it turns a side length into the area of a square. So here is our real question. How could comparing areas help us discover a length? Let us build those areas and see.

**Rendered visualization:** Change the equation panel from the route sum to squaring as area. Construct a small square as the visual bridge into the next chapter.

**Reference equation:** `4^2 + 3^2 = ?`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 01:21: Why would anyone think to square
- 01:23: Adding four and three gives seven
- 01:32: Squaring has a geometric meaning
- 01:40: How could comparing areas

## Beat 05 · 01:47–02:19

**Teaching purpose:** Viewer sees that squaring a length produces an area measured in square units, not a longer length.

**Narration:** Let us build a square on each side of our triangle. On the four-metre teal leg, we grow a square outward. Its area is four times four, which is sixteen square metres. On the three-metre gold leg, we grow another square outward. Its area is three times three, which is nine square metres. These are real geometric squares with real area — not just numbers floating in space. Each little unit cell inside those squares represents one square metre of actual floor.

**Rendered visualization:** Build a four-by-four teal grid square below the horizontal leg and a three-by-three gold grid square beside the vertical leg. Label their areas 16 and 9.

**Reference equation:** `a^2 = 4^2 = 16 \quad b^2 = 3^2 = 9`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 01:47: Let us build a square
- 01:50: On the four-metre teal leg
- 01:54: Its area is four times four
- 01:58: On the three-metre gold leg
- 02:02: Its area is three times three
- 02:12: Each little unit cell

## Beat 06 · 02:19–02:55

**Teaching purpose:** Viewer can distinguish the area of the square (25 square metres) from the side length of the square (5 metres).

**Narration:** Now add those two areas together. Sixteen plus nine equals twenty-five square metres. The claim of the Pythagorean theorem is that the square built on the diagonal — the pink side — also has an area of exactly twenty-five square metres. If that is true, then the diagonal's length must be the number whose square is twenty-five. The square root of twenty-five is five. So the diagonal is five metres. Notice: the area is twenty-five square metres, but the length is five metres. Those are different things with different units.

**Rendered visualization:** Build the true rotated five-by-five square on the diagonal. Show 16+9=25, then distinguish c squared in square metres from c in metres.

**Reference equation:** `c^2 = a^2 + b^2 = 16 + 9 = 25 \quad c = \sqrt{25} = 5`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 02:19: Now add those two areas together
- 02:28: the square built on the diagonal
- 02:32: also has an area of exactly twenty-five
- 02:42: The square root of twenty-five is five
- 02:52: Those are different things with different units

## Beat 07 · 02:55–03:25

**Teaching purpose:** Viewer can state the formula and recognise that a single numerical example is not a general proof.

**Narration:** Five lies between four and seven, so the answer passes our estimate. Now call the teal leg a, the gold leg b, and the pink diagonal c. The relationship is c squared equals a squared plus b squared. Here, twenty-five equals sixteen plus nine. But checking one example is evidence, not a proof. We still need to explain why this must work for every right triangle, including triangles with entirely different lengths.

**Rendered visualization:** Replace numerical area labels with a squared, b squared and c squared. Show the general formula, then the warning that an example is not a proof.

**Reference equation:** `c^2 = a^2 + b^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 02:56: Five lies between four and seven
- 03:00: Now call the teal leg a
- 03:05: The relationship is c squared
- 03:13: But checking one example is evidence

## Beat 08 · 03:25–03:53

**Teaching purpose:** Viewer understands the distinction between a specific numerical check and a general algebraic proof.

**Narration:** A proof must work for any positive lengths a and b. The claim is that the square on the hypotenuse has exactly the same area as both leg squares together. That is stronger than checking a few examples with a ruler or calculator. We will build an argument that does not depend on our chosen numbers. First, though, let us make sure we can identify the sides even when the triangle changes position.

**Rendered visualization:** Retain the three squares. Highlight them together and ask what area relationship remains true for arbitrary positive a and b.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 03:25: A proof must work for any positive lengths
- 03:29: The claim is that the square on the hypotenuse
- 03:41: We will build an argument

## Beat 09 · 03:53–04:22

**Teaching purpose:** Viewer can point to the hypotenuse in any orientation by locating the right-angle mark first.

**Narration:** Find the right-angle mark. The side opposite that corner is the hypotenuse: neither of its endpoints is the right-angle corner. In a right triangle it is also the longest side. We colour it pink. The two legs that meet at the right angle are teal and gold. These names describe relationships inside the triangle. They do not mean bottom side, vertical side, or whichever side happens to have an unknown label.

**Rendered visualization:** Identify the right angle and highlight the opposite pink side. Keep the legs colored teal and gold.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 03:53: Find the right-angle mark
- 03:55: The side opposite that corner
- 04:11: These names describe relationships

## Beat 10 · 04:22–04:49

**Teaching purpose:** Viewer confirms that the hypotenuse identity is preserved under rotation and is not determined by position on the page.

**Narration:** Watch the whole triangle rotate until the pink hypotenuse is at the bottom. The right-angle mark has moved to the top, but the triangle has not changed size or shape. Pink is still opposite the right angle, so it is still the hypotenuse. The formula remains c squared equals a squared plus b squared. Turning the page cannot change which side belongs on its own in that equation.

**Rendered visualization:** Rotate the full triangle through the exact angle that puts its hypotenuse horizontally below its right-angle vertex. Restore upright label orientation and retain the formula.

**Reference equation:** `c^2 = a^2 + b^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 04:23: Watch the whole triangle rotate
- 04:28: The right-angle mark has moved to the top
- 04:35: Pink is still opposite the right angle
- 04:39: The formula remains

## Beat 11 · 04:49–05:16

**Teaching purpose:** Viewer understands that the formula c² = a² + b² applies only when the angle between legs a and b is exactly 90 degrees.

**Narration:** Now keep the three-metre and four-metre legs fixed, but change the angle between them. Open the angle beyond ninety degrees: the opposite side becomes longer than five. Close it below ninety: that side becomes shorter than five. The same two lengths can produce different third sides. Three and four give five only when they meet at a right angle. That is why we check the angle before using the theorem.

**Rendered visualization:** Keep both leg lengths fixed while sweeping their included angle from 90 to 120 to 60 and back to 90 degrees. Move the opposite side with the endpoint and change the qualitative comparison.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 04:50: Now keep the three-metre and four-metre legs fixed
- 04:55: Open the angle beyond ninety degrees
- 05:01: Close it below ninety
- 05:08: Three and four give five only when

## Beat 12 · 05:16–05:42

**Teaching purpose:** Viewer can explain why adding the legs gives the route length, not the diagonal length.

**Narration:** Return the corner to ninety degrees. We have teal leg a, gold leg b, and pink hypotenuse c again. Notice that a plus b does not equal c. The sum three plus four measures the bent route, which is seven. The straight diagonal is five. The theorem combines the squares of the legs, then takes a square root. It is a different operation because we are measuring a different path.

**Rendered visualization:** Retain the right triangle. Contrast a+b with c and display the square-root formula.

**Reference equation:** `a + b \neq c \quad \text{but} \quad c^2 = a^2 + b^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 05:17: Return the corner to ninety degrees
- 05:24: Notice that a plus b does not equal c
- 05:33: The theorem combines the squares

## Beat 13 · 05:42–06:07

**Teaching purpose:** Viewer sees that four congruent right triangles fit inside the outer square with their hypotenuses forming the boundary of a central region.

**Narration:** Let us build the proof. Take a right triangle with legs a and b and hypotenuse c. Make four identical copies. Place one in each corner of an outer square, with its right angle at that corner. Around each outer edge, a leg of length a meets a leg of length b. So the outer side is a plus b. The four hypotenuses enclose a shape in the centre.

**Rendered visualization:** Place four congruent triangles at the corners of a common outer square. Label the outer side a+b and outline the actual central square.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 05:43: Let us build the proof
- 05:44: Take a right triangle
- 05:49: Make four identical copies
- 05:56: Around each outer edge
- 06:03: The four hypotenuses enclose

## Beat 14 · 06:07–06:36

**Teaching purpose:** Viewer understands that equal side lengths make a rhombus, but a square requires right angles at the corners.

**Narration:** Is that central shape really a square? Looking like a square is not enough. Each of its four sides is the hypotenuse of an identical triangle, so all four sides have length c. But equal sides alone could make a slanted rhombus. We also need right angles. Focus on one central corner. Two acute triangle angles sit beside it along a straight outer edge. Call those acute angles alpha and beta.

**Rendered visualization:** Highlight its equal sides. Add alpha and beta arcs beside one central corner along the straight outer edge.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 06:08: Is that central shape really a square
- 06:12: Each of its four sides is the hypotenuse
- 06:25: Focus on one central corner
- 06:32: Call those acute angles alpha and beta

## Beat 15 · 06:36–07:08

**Teaching purpose:** Viewer can justify that the central quadrilateral is a square by using the angle-sum property of the right triangle.

**Narration:** The angles inside a triangle total one hundred and eighty degrees. Our triangle already has a ninety-degree angle, so alpha and beta together total ninety degrees. At the central corner, alpha, the central angle, and beta lie along a straight line. The central angle is therefore one hundred and eighty minus alpha minus beta: ninety degrees. The same reasoning works at all four corners. Equal sides and right angles make the central shape a square.

**Rendered visualization:** Show the triangle angle sum, then alpha+theta+beta=180 degrees. Deduce theta=90 degrees and mark all four central right angles.

**Reference equation:** `\theta=180^\circ-(\alpha+\beta)=90^\circ`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 06:36: The angles inside a triangle total
- 06:44: so alpha and beta together total ninety degrees
- 06:48: At the central corner
- 06:53: The central angle is therefore
- 07:00: The same reasoning works at all four corners
- 07:03: Equal sides and right angles

## Beat 16 · 07:08–07:38

**Teaching purpose:** Viewer can verify the numerical case and see how the subtraction structure will generalise.

**Narration:** Check our three-four-five example. The outer side is seven, so its area is forty-nine. Each triangle has area one half times three times four, which is six. Four triangles occupy twenty-four square units. The space remaining is forty-nine minus twenty-four, or twenty-five. That is the central square's area, and its side is five. Now we will repeat this calculation with letters, so the argument covers every right triangle.

**Rendered visualization:** Use the same diagram to count 49 outer square units, 24 triangle units and 25 central square units.

**Reference equation:** `(a+b)^2 - 4 \cdot \tfrac{1}{2}ab = c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 07:09: Check our three-four-five example
- 07:14: Each triangle has area
- 07:19: Four triangles occupy twenty-four
- 07:23: The space remaining
- 07:31: Now we will repeat this calculation with letters

## Beat 17 · 07:38–08:04

**Teaching purpose:** Viewer can expand the binomial square and connect each term to a rectangular region in the diagram.

**Narration:** Keep the same picture, but replace the numbers with a and b. The outer square has side a plus b, so its area is the quantity a plus b, all squared. Multiplying a plus b by itself gives a squared, plus ab, plus another ab, plus b squared. Together those middle terms are two ab. This expression counts the whole outer square. We will now count that same area using its pieces.

**Rendered visualization:** Reuse the same proof construction. Progressively expand (a+b) squared to a squared+ab+ab+b squared, then combine the middle terms.

**Reference equation:** `(a+b)^2 = a^2 + 2ab + b^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 07:38: Keep the same picture
- 07:42: The outer square has side a plus b
- 07:48: Multiplying a plus b by itself
- 07:55: Together those middle terms
- 07:57: This expression counts the whole outer square

## Beat 18 · 08:04–08:32

**Teaching purpose:** Viewer sees that both expressions describe the total outer square area and must therefore be equal.

**Narration:** Each corner triangle has area one half times a times b. There are four identical triangles, so together their area is two ab. The central square has side c and area c squared. Add the pieces: two ab plus c squared. This is the very same outer square we counted a moment ago. Its area cannot depend on which counting method we choose, so the two expressions must be equal.

**Rendered visualization:** Highlight one triangle and then all four. Label the central area c squared and compare the two expressions for the outer area.

**Reference equation:** `a^2 + 2ab + b^2 = 2ab + c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 08:05: Each corner triangle has area
- 08:09: There are four identical triangles
- 08:14: The central square has side c
- 08:28: so the two expressions must be equal

## Beat 19 · 08:32–09:01

**Teaching purpose:** Viewer can describe the cancellation step and explain why the result holds for arbitrary positive values of a and b.

**Narration:** Set those expressions equal. A squared plus two ab plus b squared equals two ab plus c squared. Subtract two ab from both sides. Visually, that removes the same total triangle area from each count. What remains is a squared plus b squared equals c squared. That is the theorem. We used arbitrary positive lengths a and b, so this conclusion applies to every right triangle, not just our numerical example.

**Rendered visualization:** Subtract 2ab in the equation panel while fading the filled triangle regions. Retain the central square and the resulting area identity.

**Reference equation:** `a^2 + b^2 = c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 08:32: Set those expressions equal
- 08:39: Subtract two ab from both sides
- 08:41: Visually, that removes the same total triangle area
- 08:46: What remains is a squared plus b squared
- 08:51: We used arbitrary positive lengths

## Beat 20 · 09:01–09:32

**Teaching purpose:** Viewer can articulate the three logical steps that make the proof valid for all right triangles.

**Narration:** Notice what the proof depended on. Four congruent triangles, a square outside, and a square in the centre. We justified the central square using the right angle in the original triangle. Then we counted the same region twice. No measurement or lucky choice of numbers made the equation true. The algebra records an area comparison. When you remember the formula, try to remember this picture and the reason the triangle areas cancel.

**Rendered visualization:** Restore triangle fills, highlight the outer and central squares and recap the facts supporting the proof.

**Reference equation:** `a^2 + b^2 = c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 09:02: Notice what the proof depended on
- 09:09: We justified the central square
- 09:15: Then we counted the same region twice
- 09:24: When you remember the formula

## Beat 21 · 09:32–10:04

**Teaching purpose:** Viewer can identify the legs and hypotenuse in a rectangle diagonal problem.

**Narration:** Let us use the theorem to solve a real problem. A rectangular room is six metres wide and eight metres long. You want to know the length of the diagonal — the straight line from one corner to the opposite corner. First, sketch the rectangle and draw the diagonal. That diagonal is the hypotenuse of a right triangle whose legs are six metres and eight metres. Label the legs a equals six and b equals eight, and call the diagonal c. We want to find c.

**Rendered visualization:** Draw a scaled 6-by-8 rectangle and its diagonal. Identify the right angle, known legs and unknown hypotenuse.

**Reference equation:** `c^2 = 6^2 + 8^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 09:32: Let us use the theorem
- 09:46: First, sketch the rectangle and draw the diagonal
- 09:57: Label the legs

## Beat 22 · 10:04–10:36

**Teaching purpose:** Viewer can execute the full calculation and correctly take the positive square root at the final step.

**Narration:** Apply the formula. C squared equals a squared plus b squared. That is six squared plus eight squared. Six squared is thirty-six, and eight squared is sixty-four. Thirty-six plus sixty-four equals one hundred. So c squared equals one hundred. Now take the square root of both sides. The square root of one hundred is ten. Therefore c equals ten metres. Notice that we are taking the positive square root because a length cannot be negative. The diagonal is ten metres.

**Rendered visualization:** Progressively substitute 36 and 64, obtain 100, then take the positive square root. Update the diagonal label to 10 metres.

**Reference equation:** `c = \sqrt{6^2 + 8^2} = \sqrt{36 + 64} = \sqrt{100} = 10`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 10:05: Apply the formula
- 10:11: Six squared is thirty-six
- 10:15: Thirty-six plus sixty-four equals one hundred
- 10:21: Now take the square root
- 10:33: The diagonal is ten metres

## Beat 23 · 10:36–11:06

**Teaching purpose:** Viewer can apply the plausibility check to verify that the answer lies between the longer leg and the sum of both legs.

**Narration:** Does ten metres make sense? The diagonal must be longer than eight, the longer leg. It must also be shorter than the fourteen-metre route along both walls. Ten satisfies both checks. These bounds do not prove the answer is exactly ten, but they would reject fifteen immediately. The equation gives the answer; the picture helps us decide whether that answer is sensible. Both forms of reasoning belong in a complete solution.

**Rendered visualization:** Keep the rectangle and highlight its diagonal and two-leg route while showing 8 < 10 < 14.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 10:36: Does ten metres make sense
- 10:38: The diagonal must be longer than eight
- 10:42: It must also be shorter than
- 10:55: The equation gives the answer

## Beat 24 · 11:06–11:35

**Teaching purpose:** Viewer can identify and explain both common errors: confusing area with length, and adding legs instead of using the formula.

**Narration:** Watch for two different mistakes. Stopping at c squared equals one hundred does not give a length of one hundred metres. One hundred describes the square's area; taking its square root gives a side of ten metres. Area uses square metres, while length uses metres. The other mistake is adding six and eight directly. Fourteen measures the bent route. To find the diagonal, square the legs, add their squares, and take the positive root.

**Rendered visualization:** Contrast 100 square metres with 10 metres. Show that 14 metres describes the bent route, then return to the correct root calculation.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 11:06: Watch for two different mistakes
- 11:14: One hundred describes the square
- 11:23: The other mistake is adding six and eight
- 11:29: To find the diagonal

## Beat 25 · 11:35–12:05

**Teaching purpose:** Viewer correctly identifies the ladder as the hypotenuse and sets up the equation with the unknown leg h.

**Narration:** Now the unknown is a leg. In an idealized diagram, a thirteen-metre ladder reaches a vertical wall, with its foot five metres from the wall. How high does it reach? The wall and ground form the right angle. The ladder is opposite that angle, so thirteen is the hypotenuse. Label the vertical height h. Before calculating, notice that h must be less than thirteen. A vertical leg cannot be longer than the hypotenuse.

**Rendered visualization:** Draw a scaled ladder, rungs, ground and vertical wall. Identify the 13-metre hypotenuse, 5-metre base and unknown height.

**Reference equation:** `h^2 + 5^2 = 13^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 11:36: Now the unknown is a leg
- 11:39: a thirteen-metre ladder
- 11:50: The ladder is opposite that angle
- 11:58: h must be less than thirteen

## Beat 26 · 12:05–12:40

**Teaching purpose:** Viewer can rearrange the theorem to isolate an unknown leg by subtracting the known squared leg from the squared hypotenuse.

**Narration:** Write the formula with the known values. H squared plus five squared equals thirteen squared. Five squared is twenty-five, and thirteen squared is one hundred and sixty-nine. So h squared plus twenty-five equals one hundred and sixty-nine. To isolate h squared, subtract twenty-five from both sides. H squared equals one hundred and sixty-nine minus twenty-five, which is one hundred and forty-four. Now take the square root. The square root of one hundred and forty-four is twelve. So h equals twelve metres.

**Rendered visualization:** Step through h squared+25=169, subtract 25 and take the root of144. Update the vertical label to12 metres.

**Reference equation:** `h^2 = 13^2 - 5^2 = 169 - 25 = 144 \quad h = 12`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 12:06: Write the formula
- 12:17: So h squared plus twenty-five
- 12:25: H squared equals one hundred
- 12:32: Now take the square root
- 12:38: So h equals twelve metres

## Beat 27 · 12:40–13:13

**Teaching purpose:** Viewer can distinguish the add-to-find-hypotenuse structure from the subtract-to-find-leg structure.

**Narration:** Check twelve by substitution. Twelve squared plus five squared is one hundred and forty-four plus twenty-five, or one hundred and sixty-nine. That equals thirteen squared. Twelve is also less than the hypotenuse, so the answer fits the picture. Finding a leg means subtracting its partner's square from the hypotenuse's square. Finding the hypotenuse means adding the two leg squares. Identify the sides first; then let the equation tell you which operation is needed.

**Rendered visualization:** Check the numerical equation and compare formulas for a missing leg and a missing hypotenuse.

**Reference equation:** `12^2 + 5^2 = 144 + 25 = 169 = 13^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 12:41: Check twelve by substitution
- 12:53: Twelve is also less than the hypotenuse
- 12:58: Finding a leg means subtracting
- 13:03: Finding the hypotenuse means adding

## Beat 28 · 13:13–13:43

**Teaching purpose:** Viewer can use geometric reasoning to identify that adding the hypotenuse square to a leg square produces an impossible result.

**Narration:** What if someone adds thirteen squared and five squared? They get one hundred and ninety-four, whose square root is about thirteen point nine. That would make the height longer than the entire ladder. The diagram immediately exposes the mistake. The unknown is a leg, so it does not belong alone as the hypotenuse in the equation. Correcting that identification is more useful than simply saying to remember subtraction for this example.

**Rendered visualization:** Show the incorrect sum and its impossible height greater than13. Highlight the unknown leg and restore the correct equation.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 13:14: What if someone adds
- 13:19: whose square root is about thirteen point nine
- 13:29: The unknown is a leg
- 13:35: Correcting that identification

## Beat 29 · 13:43–14:14

**Teaching purpose:** Viewer accepts that the exact answer can be an irrational number and distinguishes the exact form from a decimal approximation.

**Narration:** Not every diagonal has a whole-number length. Take a square whose side is one metre. Its diagonal forms a right triangle with two one-metre legs. C squared is one plus one, or two. So c is the square root of two metres. Approximately, that is one point four one four metres. The exact square root has a decimal expansion that never ends or repeats. The radical gives an exact length; a rounded decimal gives an approximation.

**Rendered visualization:** Draw a unit square and diagonal. Calculate square root of2 and distinguish exact radical notation from the rounded approximation.

**Reference equation:** `c = \sqrt{1^2 + 1^2} = \sqrt{2} \approx 1.414`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 13:44: Not every diagonal has a whole-number length
- 13:53: C squared is one plus one
- 13:56: So c is the square root of two metres
- 13:58: Approximately, that is
- 14:08: The radical gives an exact length

## Beat 30 · 14:14–14:44

**Teaching purpose:** Viewer can extract the horizontal and vertical differences as the legs of a right triangle and apply the theorem.

**Narration:** Place two points on a coordinate grid: one comma one, and five comma four. Their horizontal difference is five minus one, or four. Their vertical difference is four minus one, or three. Draw those two perpendicular differences as the legs of a triangle. The distance between the points is its hypotenuse. Four squared plus three squared is twenty-five, so the straight-line distance is five units. The coordinates have given us the legs.

**Rendered visualization:** Plot (1,1) and (5,4) on equal-unit axes. Construct horizontal and vertical differences, then the diagonal and its length5.

**Reference equation:** `c = \sqrt{(5-1)^2 + (4-1)^2} = \sqrt{16+9} = 5`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 14:14: Place two points on a coordinate grid
- 14:20: Their horizontal difference
- 14:23: Their vertical difference
- 14:32: The distance between the points
- 14:38: so the straight-line distance is five

## Beat 31 · 14:44–15:12

**Teaching purpose:** Viewer understands that the theorem measures the straight-line displacement between two points, independent of their absolute positions.

**Narration:** Slide both points three units to the right. They are now four comma one, and eight comma four. The horizontal difference is eight minus four, still four. The vertical difference is four minus one, still three. The triangle has moved without changing shape or size, so its hypotenuse is still five. Distance depends on the difference between positions. Moving both endpoints together does not change the gap between them.

**Rendered visualization:** Translate both endpoints and their triangle three units right. Update points to(4,1),(8,4), recompute differences and retain distance5.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 14:44: Slide both points three units to the right
- 14:50: The horizontal difference is eight minus four
- 14:54: The vertical difference is four minus one
- 15:01: so its hypotenuse is still five

## Beat 32 · 15:12–15:43

**Teaching purpose:** Viewer can identify the source of the right angle in each application context.

**Narration:** A coordinate grid quietly supplies the right angle: its horizontal and vertical directions are perpendicular and use the same length units. That lets us turn coordinate differences into a right triangle. We can then calculate the straight-line separation, whether the answer is a whole number or an exact square root. We are not calculating every possible route between the points. We are calculating the direct gap across a flat plane.

**Rendered visualization:** Keep the coordinate triangle visible; highlight the perpendicular components and distinguish the direct diagonal from the two-leg route.

**Reference equation:** `a^2 + b^2 = c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 15:13: A coordinate grid quietly supplies the right angle
- 15:27: We can then calculate the straight-line separation
- 15:35: We are not calculating every possible route
- 15:38: We are calculating the direct gap

## Beat 33 · 15:43–16:10

**Teaching purpose:** Viewer attempts the calculation independently before the answer is revealed.

**Narration:** Time to try one yourself. A right triangle has legs of five metres and twelve metres. What is the length of the hypotenuse? Set up the equation: c squared equals five squared plus twelve squared. Work it out. You have eight seconds before I continue. What is c?

**Rendered visualization:** Display a correctly scaled 5-by-12 right triangle and the unanswered equation. An eight-second progress line gives thinking time without showing the answer.

**Reference equation:** `c^2 = 5^2 + 12^2`

**Thinking pause:** 8 seconds.

**Animation anchors in the narration:**

- 15:43: Time to try one yourself
- 15:50: What is the length of the hypotenuse
- 15:52: Set up the equation

## Beat 34 · 16:10–16:51

**Teaching purpose:** Viewer correctly identifies the subtraction structure needed to find the unknown leg.

**Narration:** Five squared is twenty-five, twelve squared is one hundred and forty-four, and twenty-five plus one hundred and forty-four is one hundred and sixty-nine. The square root of one hundred and sixty-nine is thirteen. So c equals thirteen metres. Now a second question. A right triangle has a hypotenuse of ten metres and one leg of six metres. What is the other leg? Set up the equation: leg squared plus six squared equals ten squared. You have eight seconds.

**Rendered visualization:** Reveal13 with its calculation. Replace the diagram with a6-8-10 triangle labeled with unknown leg h; show its equation and an eight-second thinking interval.

**Reference equation:** `c = \sqrt{169} = 13 \quad h^2 + 6^2 = 10^2`

**Thinking pause:** 8 seconds.

**Animation anchors in the narration:**

- 16:11: Five squared is twenty-five
- 16:21: The square root of one hundred and sixty-nine is thirteen
- 16:27: Now a second question
- 16:36: Set up the equation

## Beat 35 · 16:51–17:30

**Teaching purpose:** Viewer reasons from area rather than guessing, connecting the area of the square on the diagonal to the side length.

**Narration:** H squared plus thirty-six equals one hundred. Subtract thirty-six to get sixty-four, then take the positive square root: h is eight metres. Now a reasoning question. A square has sides of one metre. A student says its diagonal is two metres, because one plus one equals two. Another says the diagonal is the square root of two metres. Which student is correct? Use the areas of squares to justify your choice. Think for eight seconds.

**Rendered visualization:** Reveal8, then replace the triangle with a unit square. Present2 and square root of2 as neutral candidates, followed by eight seconds of thinking.

**Reference equation:** `h = \sqrt{64} = 8`

**Thinking pause:** 8 seconds.

**Animation anchors in the narration:**

- 16:51: H squared plus thirty-six equals one hundred
- 16:54: Subtract thirty-six to get sixty-four
- 16:59: h is eight metres
- 17:01: Now a reasoning question
- 17:05: A student says its diagonal is two metres
- 17:11: Another says the diagonal is the square root of two

## Beat 36 · 17:30–17:57

**Teaching purpose:** Viewer can use the area of the square on the hypotenuse to justify why the diagonal is √2 and not 2.

**Narration:** The diagonal is the square root of two metres. The squares on the two legs each have area one square metre, so the square on the diagonal must have area two. Its side is therefore the square root of two. If that side were two metres, its square would have area four, which contradicts our area relationship. The length two measures the bent route along two edges, not the diagonal across the square.

**Rendered visualization:** Reveal square root of2. Use the equation panel to compare areas2 and4, then highlight the two-edge route and the shorter diagonal.

**Reference equation:** `c^2 = 1^2 + 1^2 = 2 \quad c = \sqrt{2} \neq 2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 17:30: The diagonal is the square root of two metres
- 17:33: The squares on the two legs each have area one
- 17:44: If that side were two metres
- 17:50: The length two measures the bent route

## Beat 37 · 17:57–18:26

**Teaching purpose:** Viewer connects the final answer back to the opening question and appreciates the two-metre difference.

**Narration:** Return to our robot. Four metres east and three metres north form the two legs. Their squares have areas sixteen and nine, totalling twenty-five. So the diagonal's square has area twenty-five and its side is five metres. Let the robot take that straight path now. It travels five metres instead of seven, saving two metres. We have answered the opening question, and we can explain the answer rather than just announcing it.

**Rendered visualization:** Return to the original robot triangle. Calculate5 and move the dot along the diagonal; show the two-metre saving.

**Reference equation:** `c = \sqrt{4^2 + 3^2} = \sqrt{25} = 5`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 17:58: Return to our robot
- 18:03: Their squares have areas sixteen and nine
- 18:10: and its side is five metres
- 18:12: Let the robot take that straight path now
- 18:15: It travels five metres instead of seven

## Beat 38 · 18:26–18:56

**Teaching purpose:** Viewer can narrate the area-conservation argument from memory without referring to specific numbers.

**Narration:** Remember the connection. The leg lengths define two square areas. Our proof shows that their sum equals the area of the hypotenuse square. We established that by counting one outer square in two ways and subtracting the same triangle areas. Finally, a square root converts the resulting area back into a length. The geometry explains the equation, and the equation lets us calculate a distance that would be difficult to measure directly.

**Rendered visualization:** Rebuild the three outward squares and their numerical area labels. Connect the proven area identity to the square-root length formula.

**Reference equation:** `a^2 + b^2 = c^2 \quad (16 + 9 = 25)`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 18:26: Remember the connection
- 18:28: The leg lengths define two square areas
- 18:30: Our proof shows that their sum
- 18:42: Finally, a square root converts

## Beat 39 · 18:56–19:27

**Teaching purpose:** Viewer can reproduce the six-step checklist and explain the purpose of each step.

**Narration:** Before using the theorem, check for a right angle and identify the side opposite it. That is the hypotenuse. Square the known lengths, then add or subtract according to which side is missing. Take the positive square root and state the length unit. Check the result against the picture: a hypotenuse exceeds either leg but is shorter than their sum; an unknown leg must be shorter than the known hypotenuse. Every check has a geometric reason.

**Rendered visualization:** Keep the squares visible while progressing through the right-angle, hypotenuse, calculation, units and plausibility checks.

**Reference equation:** ``

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 18:56: Before using the theorem
- 19:04: Square the known lengths
- 19:09: Take the positive square root
- 19:12: Check the result against the picture
- 19:19: an unknown leg must be shorter

## Beat 40 · 19:27–20:00

**Teaching purpose:** Viewer can explain in their own words why adding the legs gives the route length and why the theorem gives the diagonal length, grounding the answer in the area-conservation proof.

**Narration:** Try explaining one final idea in your own words: why does four plus three not give the diagonal? It measures a route with a turn. The diagonal crosses directly between the same endpoints. To find its length, we compare square areas instead. The square on the hypotenuse equals the two leg squares together because a right triangle lets us build two equal counts of the same area. Taking the square root turns that area relationship into the length of our shortcut.

**Rendered visualization:** Contrast the bent route with the direct diagonal. Highlight the three square areas and end on the area identity and its explanation.

**Reference equation:** `a^2 + b^2 = c^2`

**Thinking pause:** 0 seconds.

**Animation anchors in the narration:**

- 19:27: Try explaining one final idea
- 19:35: It measures a route with a turn
- 19:37: The diagonal crosses directly
- 19:44: The square on the hypotenuse equals
- 19:54: Taking the square root
