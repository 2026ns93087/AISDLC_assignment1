# Harness Log: Part 1B Natural-Language Reminder Agent

## 1. Specification and task context given before generation

For Part 1B, I built a Natural-Language Reminder Agent. The basic idea is simple: the user types a reminder request in normal English, and the agent uses Google Gemini to understand it and return the required JSON output.
Before starting the implementation, I had the main requirements, acceptance criteria, rules and evaluation metrics defined. One important rule was that if Gemini gives an invalid response, the program should reject it instead of quietly trying to fix it.
The specification was approved before the final implementation and I kept it unchanged during the actual evaluation.

## 2. Initial generation

The first version had the main parts needed for the reminder agent, such as CLI handling, Gemini connection, configuration, prompts, validation and reminder logic.
The agent can handle five types of actions:

- create
- reschedule
- snooze
- clarify
- unsupported
Gemini is expected to return a valid JSON response. If the response does not follow the required format, the program rejects it.
I also kept a copy of the initial source code and prompts in the evidence folder so I could compare them with the final version later.

## 3. Harness design and self-check

I created the harness to check whether the agent was actually working correctly and not just giving reasonable-looking answers.
I mainly checked three things:

- Layer 1: Is the JSON format correct?
- Layer 2: Does the output follow the important rules and guardrails?
- Layer 3: Does the answer match what we expected for that request?
I also tried some intentionally bad model responses, like invalid JSON, wrong intent, wrong reminder time and simulated API failures. The harness was able to catch these problems.
The final result can be PASS, FAIL or INCOMPLETE. For example, if the Gemini API is down and the test cannot complete, I don't count that as a PASS.

## 4. Evaluation configuration (model, thresholds and scoring)

I used gemini-3.5-flash-lite with temperature 0 for the evaluation.
The dataset had 40 test cases covering different situations such as normal reminder requests, missing information, invalid input, boundary cases and ambiguous requests.
The evaluation checked things like:

- JSON format
- Correct intent
- Reminder time and target
- Clarification responses
- Guardrails
- Invalid input handling
The main thresholds were decided before running the real evaluation. This was important because I didn't want to change the passing criteria later just because a test failed.

## 5. Evaluation runs and outcomes

The initial static checks passed.
When I ran the first real evaluation, it FAILED, even though most of the results looked good. Most of the problem came from one test case, EV-026.
I fixed the issue in the prompt and ran the same evaluation again.
The second run PASSED and met all the required thresholds.
I also ran the static checks again after the fix, and they passed as well.

## 6. Failure and repair cycle

The main failed case was:
"Reschedule my dentist reminder"
The user wanted to reschedule the reminder but didn't mention the new time.
Gemini actually understood that it needed to ask the user for the missing time. The problem was that it also returned the existing reminder ID in target_id.
According to my rules, target_id should be null when the agent is asking for clarification.
I tried the case again and saw the same problem. So I made a small change to prompts/system.md to clearly tell Gemini that target_id must stay null for a clarification response.
After making this change, I ran the evaluation again and it passed.

## 7. Failure evidence supplied to the coding agent

For the failed case, I kept the user request, Gemini's response, what I expected and what actually happened.
I also had repeated model responses that showed the same issue, which helped confirm that it wasn't just a random one-time failure.
I didn't change the dataset or lower the thresholds just to make the test pass. The fix was made in the prompt instead.

## 8. What changed after repair and re-evaluation

The main change was quite small. I updated prompts/system.md to make the clarification rule more clear.
There was also an earlier configuration-related change in src/config.py.
For the second evaluation, I kept the same dataset and thresholds. After the prompt fix, the evaluation passed.
So there wasn't a major rewrite of the solution. It was mostly about making one instruction clearer based on what I saw in the failed run.

## 9. Final human decision, known limitations and justification

Based on the final results, my decision is ACCEPT. The evaluation passed after fixing the prompt, without changing the dataset or thresholds.
There are still some limitations, such as the small dataset, possible variation in Gemini responses, and testing mainly in English. Incorrect reminder time also remains an important risk.
Overall, the implementation works well for the tested cases, but more test cases and repeated evaluations would improve confidence.
