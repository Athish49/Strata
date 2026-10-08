# Answering guide: offline judge batches

You are standing in for the judge LLM. For every entry in `batch_NN.json`
(`{"id", "prompt_sha256", "system", "user"}`) do exactly what the model would do:

1. Read the entry's `system` prompt in full; it is the task definition and decision rule. Follow it literally.
2. Read the `user` message. Judge ONLY from the texts it contains (change summary, word diff,
   S1/S2 text, clause text, parameters). No outside knowledge, no guessing about other documents,
   no looking at any other files, scores or expected results.
3. Answer ONE JSON object per entry that matches `JudgeResult`:
   `{"affected": bool, "finding_type": <one of the types in the system prompt>, "severity": "low|medium|high"
   as defined in the prompt, "required_change": object or null, "quotes": {"s1": ..., "s2": ..., "clause": ...},
   "rationale": str, "confidence": number 0..1}`.
   Use exactly the enum spellings the system prompt lists.
4. Quotes must be VERBATIM substrings (copy-paste, same case, same punctuation) of the S1 text, S2 text and
   clause text respectively. `quotes.clause` is required when `affected` is true. Use null for an absent S1/S2.
5. `rationale`: at most 60 words, plain, factual, referring only to what is in the prompt.
6. `confidence`: 0..1, honest. Lower it when the match is indirect or the texts are ambiguous.
7. Be conservative per the prompt's decision rule: if the clause is not clearly affected by the change,
   `affected=false` (still give finding_type, severity, empty quotes object values, short rationale).
   Never speculate; never mark affected on a citation alone.

Output file: `answers_NN.json` next to `batch_NN.json` (same NN), a JSON array
`[{"id": "<candidate id from the batch>", "answer": { ...JudgeResult... }}]`, one item per batch entry,
valid JSON only (no comments, no trailing commas). Do not edit `prompt_sha256`, `system` or `user`.
Do not run the import script; the lead loads the answers.
