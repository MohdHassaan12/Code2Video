# Why the Pythagorean Theorem Works

Original premium-model draft, reviewed and rendered by the coding agent. Synthetic English narration.

## 00:00 — THE SHORTCUT

Picture a rectangular warehouse floor. A robot starts at the bottom-left corner and needs to reach the top-right corner. It could travel four metres east, then three metres north. That route covers seven metres. But the robot can also drive straight across the diagonal. How long is that shortcut? By the end, you will be able to calculate it and explain why the calculation works.

Look at those three line segments: the four-metre bottom, the three-metre side, and the diagonal. Together they form a triangle. Where the two legs meet, the corner is a right angle, because the floor is rectangular. The little corner mark tells us it is exactly ninety degrees. Keep watching that mark. It is the condition that makes the relationship we are about to discover possible.

Before calculating, estimate. The diagonal is longer than either leg, so it is more than four metres. But the straight path is shorter than the bent, seven-metre route between the same endpoints. Our answer must lie between four and seven. We do not know it yet, but we already know something useful. An estimate gives us a way to challenge an answer instead of trusting every number a calculation produces.

Why would anyone think to square the side lengths? Adding four and three gives seven, the route along the walls. Multiplying gives twelve, but that is not the length of the diagonal either. Squaring has a geometric meaning: it turns a side length into the area of a square. So here is our real question. How could comparing areas help us discover a length? Let us build those areas and see.

## 01:47 — LENGTH BECOMES AREA

Let us build a square on each side of our triangle. On the four-metre teal leg, we grow a square outward. Its area is four times four, which is sixteen square metres. On the three-metre gold leg, we grow another square outward. Its area is three times three, which is nine square metres. These are real geometric squares with real area — not just numbers floating in space. Each little unit cell inside those squares represents one square metre of actual floor.

Now add those two areas together. Sixteen plus nine equals twenty-five square metres. The claim of the Pythagorean theorem is that the square built on the diagonal — the pink side — also has an area of exactly twenty-five square metres. If that is true, then the diagonal's length must be the number whose square is twenty-five. The square root of twenty-five is five. So the diagonal is five metres. Notice: the area is twenty-five square metres, but the length is five metres. Those are different things with different units.

Five lies between four and seven, so the answer passes our estimate. Now call the teal leg a, the gold leg b, and the pink diagonal c. The relationship is c squared equals a squared plus b squared. Here, twenty-five equals sixteen plus nine. But checking one example is evidence, not a proof. We still need to explain why this must work for every right triangle, including triangles with entirely different lengths.

A proof must work for any positive lengths a and b. The claim is that the square on the hypotenuse has exactly the same area as both leg squares together. That is stronger than checking a few examples with a ruler or calculator. We will build an argument that does not depend on our chosen numbers. First, though, let us make sure we can identify the sides even when the triangle changes position.

## 03:53 — IDENTIFY THE RIGHT SIDE

Find the right-angle mark. The side opposite that corner is the hypotenuse: neither of its endpoints is the right-angle corner. In a right triangle it is also the longest side. We colour it pink. The two legs that meet at the right angle are teal and gold. These names describe relationships inside the triangle. They do not mean bottom side, vertical side, or whichever side happens to have an unknown label.

Watch the whole triangle rotate until the pink hypotenuse is at the bottom. The right-angle mark has moved to the top, but the triangle has not changed size or shape. Pink is still opposite the right angle, so it is still the hypotenuse. The formula remains c squared equals a squared plus b squared. Turning the page cannot change which side belongs on its own in that equation.

Now keep the three-metre and four-metre legs fixed, but change the angle between them. Open the angle beyond ninety degrees: the opposite side becomes longer than five. Close it below ninety: that side becomes shorter than five. The same two lengths can produce different third sides. Three and four give five only when they meet at a right angle. That is why we check the angle before using the theorem.

Return the corner to ninety degrees. We have teal leg a, gold leg b, and pink hypotenuse c again. Notice that a plus b does not equal c. The sum three plus four measures the bent route, which is seven. The straight diagonal is five. The theorem combines the squares of the legs, then takes a square root. It is a different operation because we are measuring a different path.

## 05:42 — BUILD A PROOF

Let us build the proof. Take a right triangle with legs a and b and hypotenuse c. Make four identical copies. Place one in each corner of an outer square, with its right angle at that corner. Around each outer edge, a leg of length a meets a leg of length b. So the outer side is a plus b. The four hypotenuses enclose a shape in the centre.

Is that central shape really a square? Looking like a square is not enough. Each of its four sides is the hypotenuse of an identical triangle, so all four sides have length c. But equal sides alone could make a slanted rhombus. We also need right angles. Focus on one central corner. Two acute triangle angles sit beside it along a straight outer edge. Call those acute angles alpha and beta.

The angles inside a triangle total one hundred and eighty degrees. Our triangle already has a ninety-degree angle, so alpha and beta together total ninety degrees. At the central corner, alpha, the central angle, and beta lie along a straight line. The central angle is therefore one hundred and eighty minus alpha minus beta: ninety degrees. The same reasoning works at all four corners. Equal sides and right angles make the central shape a square.

Check our three-four-five example. The outer side is seven, so its area is forty-nine. Each triangle has area one half times three times four, which is six. Four triangles occupy twenty-four square units. The space remaining is forty-nine minus twenty-four, or twenty-five. That is the central square's area, and its side is five. Now we will repeat this calculation with letters, so the argument covers every right triangle.

## 07:38 — COUNT THE SAME AREA TWICE

Keep the same picture, but replace the numbers with a and b. The outer square has side a plus b, so its area is the quantity a plus b, all squared. Multiplying a plus b by itself gives a squared, plus ab, plus another ab, plus b squared. Together those middle terms are two ab. This expression counts the whole outer square. We will now count that same area using its pieces.

Each corner triangle has area one half times a times b. There are four identical triangles, so together their area is two ab. The central square has side c and area c squared. Add the pieces: two ab plus c squared. This is the very same outer square we counted a moment ago. Its area cannot depend on which counting method we choose, so the two expressions must be equal.

Set those expressions equal. A squared plus two ab plus b squared equals two ab plus c squared. Subtract two ab from both sides. Visually, that removes the same total triangle area from each count. What remains is a squared plus b squared equals c squared. That is the theorem. We used arbitrary positive lengths a and b, so this conclusion applies to every right triangle, not just our numerical example.

Notice what the proof depended on. Four congruent triangles, a square outside, and a square in the centre. We justified the central square using the right angle in the original triangle. Then we counted the same region twice. No measurement or lucky choice of numbers made the equation true. The algebra records an area comparison. When you remember the formula, try to remember this picture and the reason the triangle areas cancel.

## 09:32 — WORKED PROBLEM ONE

Let us use the theorem to solve a real problem. A rectangular room is six metres wide and eight metres long. You want to know the length of the diagonal — the straight line from one corner to the opposite corner. First, sketch the rectangle and draw the diagonal. That diagonal is the hypotenuse of a right triangle whose legs are six metres and eight metres. Label the legs a equals six and b equals eight, and call the diagonal c. We want to find c.

Apply the formula. C squared equals a squared plus b squared. That is six squared plus eight squared. Six squared is thirty-six, and eight squared is sixty-four. Thirty-six plus sixty-four equals one hundred. So c squared equals one hundred. Now take the square root of both sides. The square root of one hundred is ten. Therefore c equals ten metres. Notice that we are taking the positive square root because a length cannot be negative. The diagonal is ten metres.

Does ten metres make sense? The diagonal must be longer than eight, the longer leg. It must also be shorter than the fourteen-metre route along both walls. Ten satisfies both checks. These bounds do not prove the answer is exactly ten, but they would reject fifteen immediately. The equation gives the answer; the picture helps us decide whether that answer is sensible. Both forms of reasoning belong in a complete solution.

Watch for two different mistakes. Stopping at c squared equals one hundred does not give a length of one hundred metres. One hundred describes the square's area; taking its square root gives a side of ten metres. Area uses square metres, while length uses metres. The other mistake is adding six and eight directly. Fourteen measures the bent route. To find the diagonal, square the legs, add their squares, and take the positive root.

## 11:35 — WORKED PROBLEM TWO

Now the unknown is a leg. In an idealized diagram, a thirteen-metre ladder reaches a vertical wall, with its foot five metres from the wall. How high does it reach? The wall and ground form the right angle. The ladder is opposite that angle, so thirteen is the hypotenuse. Label the vertical height h. Before calculating, notice that h must be less than thirteen. A vertical leg cannot be longer than the hypotenuse.

Write the formula with the known values. H squared plus five squared equals thirteen squared. Five squared is twenty-five, and thirteen squared is one hundred and sixty-nine. So h squared plus twenty-five equals one hundred and sixty-nine. To isolate h squared, subtract twenty-five from both sides. H squared equals one hundred and sixty-nine minus twenty-five, which is one hundred and forty-four. Now take the square root. The square root of one hundred and forty-four is twelve. So h equals twelve metres.

Check twelve by substitution. Twelve squared plus five squared is one hundred and forty-four plus twenty-five, or one hundred and sixty-nine. That equals thirteen squared. Twelve is also less than the hypotenuse, so the answer fits the picture. Finding a leg means subtracting its partner's square from the hypotenuse's square. Finding the hypotenuse means adding the two leg squares. Identify the sides first; then let the equation tell you which operation is needed.

What if someone adds thirteen squared and five squared? They get one hundred and ninety-four, whose square root is about thirteen point nine. That would make the height longer than the entire ladder. The diagram immediately exposes the mistake. The unknown is a leg, so it does not belong alone as the hypotenuse in the equation. Correcting that identification is more useful than simply saying to remember subtraction for this example.

## 13:43 — BEYOND WHOLE NUMBERS

Not every diagonal has a whole-number length. Take a square whose side is one metre. Its diagonal forms a right triangle with two one-metre legs. C squared is one plus one, or two. So c is the square root of two metres. Approximately, that is one point four one four metres. The exact square root has a decimal expansion that never ends or repeats. The radical gives an exact length; a rounded decimal gives an approximation.

Place two points on a coordinate grid: one comma one, and five comma four. Their horizontal difference is five minus one, or four. Their vertical difference is four minus one, or three. Draw those two perpendicular differences as the legs of a triangle. The distance between the points is its hypotenuse. Four squared plus three squared is twenty-five, so the straight-line distance is five units. The coordinates have given us the legs.

Slide both points three units to the right. They are now four comma one, and eight comma four. The horizontal difference is eight minus four, still four. The vertical difference is four minus one, still three. The triangle has moved without changing shape or size, so its hypotenuse is still five. Distance depends on the difference between positions. Moving both endpoints together does not change the gap between them.

A coordinate grid quietly supplies the right angle: its horizontal and vertical directions are perpendicular and use the same length units. That lets us turn coordinate differences into a right triangle. We can then calculate the straight-line separation, whether the answer is a whole number or an exact square root. We are not calculating every possible route between the points. We are calculating the direct gap across a flat plane.

## 15:43 — YOUR TURN

Time to try one yourself. A right triangle has legs of five metres and twelve metres. What is the length of the hypotenuse? Set up the equation: c squared equals five squared plus twelve squared. Work it out. You have eight seconds before I continue. What is c?

[Thinking pause: 8 seconds]

Five squared is twenty-five, twelve squared is one hundred and forty-four, and twenty-five plus one hundred and forty-four is one hundred and sixty-nine. The square root of one hundred and sixty-nine is thirteen. So c equals thirteen metres. Now a second question. A right triangle has a hypotenuse of ten metres and one leg of six metres. What is the other leg? Set up the equation: leg squared plus six squared equals ten squared. You have eight seconds.

[Thinking pause: 8 seconds]

H squared plus thirty-six equals one hundred. Subtract thirty-six to get sixty-four, then take the positive square root: h is eight metres. Now a reasoning question. A square has sides of one metre. A student says its diagonal is two metres, because one plus one equals two. Another says the diagonal is the square root of two metres. Which student is correct? Use the areas of squares to justify your choice. Think for eight seconds.

[Thinking pause: 8 seconds]

The diagonal is the square root of two metres. The squares on the two legs each have area one square metre, so the square on the diagonal must have area two. Its side is therefore the square root of two. If that side were two metres, its square would have area four, which contradicts our area relationship. The length two measures the bent route along two edges, not the diagonal across the square.

## 17:57 — RETURN TO THE QUESTION

Return to our robot. Four metres east and three metres north form the two legs. Their squares have areas sixteen and nine, totalling twenty-five. So the diagonal's square has area twenty-five and its side is five metres. Let the robot take that straight path now. It travels five metres instead of seven, saving two metres. We have answered the opening question, and we can explain the answer rather than just announcing it.

Remember the connection. The leg lengths define two square areas. Our proof shows that their sum equals the area of the hypotenuse square. We established that by counting one outer square in two ways and subtracting the same triangle areas. Finally, a square root converts the resulting area back into a length. The geometry explains the equation, and the equation lets us calculate a distance that would be difficult to measure directly.

Before using the theorem, check for a right angle and identify the side opposite it. That is the hypotenuse. Square the known lengths, then add or subtract according to which side is missing. Take the positive square root and state the length unit. Check the result against the picture: a hypotenuse exceeds either leg but is shorter than their sum; an unknown leg must be shorter than the known hypotenuse. Every check has a geometric reason.

Try explaining one final idea in your own words: why does four plus three not give the diagonal? It measures a route with a turn. The diagonal crosses directly between the same endpoints. To find its length, we compare square areas instead. The square on the hypotenuse equals the two leg squares together because a right triangle lets us build two equal counts of the same area. Taking the square root turns that area relationship into the length of our shortcut.
