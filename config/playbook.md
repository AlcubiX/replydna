# Reply playbook

Claude reads `config/voice_card.md` first, then this playbook, before writing any reply.

## 1. Comment types (labels)
| Group | Categories | Default action |
|---|---|---|
| 🟢 Easy wins | praise, generic_praise, superfan, success_story, beginner_question, topic_request | reply (short, warm, specific) |
| 🔵 Value | advanced_question, wants_to_learn, offer_question, factual_correction, outdated_info | reply with one useful point |
| 🟡 Judgement | troll, valid_criticism, joke_but_valid, blame, selling_accusation, competitor_comparison | **two drafts: A calm, B witty** |
| 🔴 Alerts (you only) | fraud_claim, distress, legal_threat, customer_complaint | `alert`: never auto-replied |
| ⏸ Hold | scam, impersonation, personal_info, abuse, spam | `hold` (reversible) |
| ⚪ Careful | advice_request (asks for personal financial / medical / legal advice) | general info + your disclaimer, never personal advice |

Every label carries: tone, validity (specific/vague), trust pillar (ability / integrity / benevolence),
severity, urgency, evidence (the words that decided it), reason and confidence.

## 2. Reply rules
- **Language mirror is a hard rule.** Reply in exactly the commenter's language **and** script:
  Hinglish (Roman) → Hinglish (Roman); Devanagari Hindi → Devanagari Hindi; English → English; Spanish → Spanish; any language → that language.
  For a mixed comment, follow the dominant language. Mirror formality too (aap/tum, usted/tú, vous/tu).
- Voice card first. 1-3 short lines. One useful point. Each reply unique (never copy-paste).
- At most **one** signature phrase per reply: signature, not caricature.
- Never: insults or slurs; comments on family, looks, caste, religion, gender or region; threats; personal info; lies;
  guarantees; anything in `never_say` from the profile.
- Trolls: reply only if the comment is visible (has likes) and the reply teaches the audience something. Otherwise hold or ignore.
  One reply per troll, never a "last word" fight. Use the profile's savage level for option B.
- Valid criticism goes on the fix-list for the monthly report. A factual correction gets a thank-you + "worth pinning a correction?".
- Distress: kind, short, no advice, point to `crisis_line` from the profile, and alert the creator.
- Fraud claims: never argue in public. One calm, factual line, approved by the creator (template in the voice card).

## 3. Offer rules (course / product / membership)
- Only on **pull**: offer_question, wants_to_learn, an advanced question a comment can't fully answer, or the same person's 3rd+ question.
- **Never** on blame, distress, troll, valid_criticism, success_story, customer_complaint, advice_request, fraud_claim.
- Value first: one useful free line before any mention. Facts only from `config/offer.md` (✅ lines).
- No income claims, no fake urgency, no discounts unless the creator confirms one is live. Link only when asked.
- Cap: ≤ 10% of a day's replies. Unprompted mentions to one person at most once per 30 days.
- Tracking: add `?utm_source=youtube&utm_medium=comment_reply&utm_campaign=<category>` to offer links.
  Watch the "just selling" complaint rate; if it rises, mention the offer less often.

## 4. Threads (conversations)
- Reply only when the viewer replies. Never double-reply, never chase someone who went silent.
- **Continue** while the viewer moves forward (details, price, link, "how do I join"). Tag the thread `hot_lead`
  so it shows up in the inbox under 🔥 Hot leads. Never ask for a phone number or email in public.
- **Stop** (`closed`) when it turns off-topic, becomes an argument, repeats a fully answered question
  (one final reply pointing to the website), or turns abusive (hold).
- At most **4 assistant replies per thread**; after that it is handed to the creator.

## 5. Other channels (mentions radar)
- Read-only. Never post, hide, report or ban on someone else's channel.
- Label comments there with `about_creator` true/false. Show suggestions only; the creator decides.
- Always surface negative-title videos and look-alike channels ("yours, a fan page, or fake?").
