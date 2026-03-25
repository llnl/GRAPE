## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

### Available skills
- address-reviewer-comments: Gather unresolved GitLab merge request comments with `grape -d review --printUnresolvedComments`, fix trivial review feedback, verify the fixes, commit the result, and summarize how each comment was addressed. Use when asked to address review feedback on a branch in this repository. (file: .agents/skills/address-reviewer-comments/SKILL.md)

### How to use skills
- Discovery: The list above is the skills available in this repository for this session. Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill with `$SkillName` or plain text, or the task clearly matches a listed description, use that skill for that turn.
- How to use a skill: Read only enough of the `SKILL.md` body to follow the workflow. Load referenced files only when they are needed.
- Safety: If a skill cannot be applied cleanly, state the issue briefly and continue with the best fallback.
