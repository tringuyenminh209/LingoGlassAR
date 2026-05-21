---
name: nippo
description: Write the daily Japanese work report (`docs/nippo/YYYY-MM-DD.md`) for LingoGlass AR. Use when the user says "update nippo" / "nippo 書いて" / "write the nippo" / "日報" / "nippo cập nhật", or at end-of-day if the user asks for it. Generates a new file or appends an addendum to the existing same-day file; never overwrites prior sections. Reads `git log` of the day and the previous nippo for context; only writes facts the conversation actually contains.
---

# Nippo (daily report) skill

Single source of truth for the daily work-log format used in this repo. The format is set by the existing files in `docs/nippo/`; treat those as the style spec.

## When to invoke

The user says one of:
- "update nippo" / "nippo cập nhật" / "nippo 書いて" / "日報"
- "write today's report"
- "log today's work"
- end-of-day summary requests like "まとめて" when the working context is a coding session

Do **not** invoke for casual status questions ("what did we do today?"). The skill writes a file; a chat reply is not a nippo.

## Output path

```
docs/nippo/YYYY-MM-DD.md
```

`YYYY-MM-DD` is **today** per the system reminder (`Today's date is …`). Do not derive the date from `git log` or system clock — the system reminder is authoritative.

Filename day of week is the Japanese single-character form (月火水木金土日) in the H1 title only, not the filename.

## New file vs addendum

Before writing, **read the existing same-day file** if it exists.

| Situation | Action |
| --- | --- |
| File does not exist | Create with the full standard skeleton (sections below) |
| File exists, last section is "次回の予定" or earlier | Append a `## 追記: <topic> (YYYY-MM-DD <時刻帯>)` section at the bottom. Never edit prior sections. |
| File exists, already has 追記 sections | Append a new `## 追記:` section after the last one. Keep the existing chain intact. |

`<時刻帯>` is one of `朝` / `昼` / `夕方` / `夜` / `深夜` based on local time when called. Use `深夜` for >22:00.

If multiple sprint days closed in one calendar day (like 2026-05-21 closing Day 2-7), each addendum gets its own section. The structure already on file is the right template.

## Standard skeleton (new file)

```markdown
# 日報 - YYYY-MM-DD (曜)

## 作業者
グエン・ミン・チ (solo founder / dev)

## 担当
<one line: which sprint / phase / day, what subsystem>

## 本日の作業時間
約 N 時間 (<short categorical breakdown>)

## 本日の作業内容

### 1. <topic>
<bulleted or paragraph form, concrete facts only>

### 2. <topic>
...

## 本日のコミット (origin/main pushed)

| Hash | 内容 |
|---|---|
| `abcdef1` | commit subject line |
...

## 課題・懸念

- ...

## 次回の予定 (YYYY-MM-DD〜)

<concrete next-day tasks, not vague intentions>
```

`担当` line is one sentence. `作業時間` is approximate hours; if the user did not state it, write `(self-reported)` and ask the user before committing — or skip the section and let them fill it.

## Standard skeleton (addendum)

```markdown
## 追記: <one-line topic> (YYYY-MM-DD <時刻帯>)

<2-4 sentence framing of what got done in this slice>

### <subsection if needed>

| Hash | 内容 |
|---|---|
| ... | ... |

### 学び (optional)

1. ...
```

The framing paragraph is mandatory because it lets the reader skip a section that does not concern them. Keep it factual ("Day 5 + Day 6 + Day 7 まで押し切った"), not motivational.

## Data sources to consult before writing

In this order:
1. **The conversation itself.** Every fact you write must already exist in the conversation; the nippo is documentation, not invention.
2. **`git log --since='YYYY-MM-DD 00:00' --pretty=format:'%h %ad %s' --date=format:'%Y-%m-%d %H:%M'`** for the commit table. Include only commits with `origin/main` (pushed) — note this in the section header. If a commit is local-only, mark it `(local)` in the table.
3. **Previous nippo files in `docs/nippo/`** (read at least the most recent one) to match section ordering, terminology, and granularity. Do not duplicate prior days' content.
4. **`docs/codex/S1_TASKS.md`** or analogous sprint-tracker file if the day touched Codex tasks. Cite PR numbers and review follow-ups verbatim.
5. **Memory files in `.../memory/`** if the day's work created a new memory entry — note the new entry in `本日のメモリー追加`.

Never invent timing, hours, costs, or numeric measurements. If a number is not in the conversation, omit it or write `(未計測)`.

## Style rules (locked)

- **Language: Japanese.** This is non-negotiable; the project's nippo trail is uniformly Japanese. Even if the conversation was in Vietnamese, the nippo is Japanese.
- **Concrete > abstract.** "PR #5 マージ (`c5de0ff`), audio recorder 24 kHz PCM16 100 ms チャンク" not "audio recording feature implemented."
- **Half-width parens for code/identifiers**, full-width parens (（）) for Japanese commentary if mixing — but consistency with prior nippo wins.
- **Tables for commits and review checklists.** Bullets for analysis / 学び / 課題.
- **No emoji** unless the existing same-day file already uses them.
- **No Claude self-references.** Write as if the user authored the file. "Claude (自分) が" is the established convention when referring to the implementer-self during a Claude+Codex split, mirroring the existing 2026-05-21 style.
- **Privacy boundary applies here too.** Never copy user audio bytes, translated text content, OpenAI tokens, or API keys into the nippo. Counts, durations, and error codes are fine.

## Commit handling

After writing the file:

1. `git add docs/nippo/YYYY-MM-DD.md`
2. Commit with subject `docs(nippo): YYYY-MM-DD <one-line summary>` — match prior nippo commits (look at recent `git log -- docs/nippo/` for the established subject style).
3. **Never add a `Co-Authored-By: Claude` trailer.** This is a hard rule from `feedback-no-claude-coauthor` memory.
4. Push only if the user asked for it or if recent nippo commits in `git log` show the user pushes them immediately.

If the user has uncommitted unrelated changes in the working tree, stage **only** the nippo file (`git add docs/nippo/...`), not `-A` / `-u`.

## What this skill does NOT do

- Does not summarise other people's work (solo project — only one author).
- Does not write English summaries; the nippo is for the Japanese workflow journal.
- Does not generate PR descriptions, release notes, or commit messages for non-nippo files — those have their own conventions in `CLAUDE.md`.
- Does not predict next-day work beyond what the conversation explicitly stated. "Day 8 着手" is fine if the user said so; "perhaps optimize X" is not.

## Checklist before declaring nippo done

- [ ] File path is `docs/nippo/YYYY-MM-DD.md` with today's date from system reminder.
- [ ] H1 includes Japanese single-character weekday in parentheses.
- [ ] Every commit hash in the table appears in `git log --since='YYYY-MM-DD 00:00'`.
- [ ] No facts that the conversation did not already contain.
- [ ] If addendum: prior sections untouched, new section appended at bottom with `時刻帯` tag.
- [ ] Commit subject matches the `docs(nippo): YYYY-MM-DD …` pattern of prior commits.
- [ ] No Claude co-author trailer.
- [ ] Privacy: no audio / translated text / tokens / API keys in the file.
