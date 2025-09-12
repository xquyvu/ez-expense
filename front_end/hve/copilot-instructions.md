# Copilot instructions

## Breadcrumb Protocol

A breadcrumb is a collaborative scratch pad that allow the user and agent to get alignment on context. When working on tasks in this folder,
follow this collaborative documentation workflow to create a clear trail of decisions and implementations:

1. At the start of each new task, ask me for a breadcrumb file name if you can't determine a suitable one.

2. Create the breadcrumb file in the `front_end/hve` folder using the format:
   `yyyy-mm-dd-HHMM-{title}.md` (*year-month-date-current_time_in-24hr_format-{title}.md* using UTC timezone)

3. Structure the breadcrumb file with these required sections:
   - **Requirements**: Clear list of what needs to be implemented.
   - **Plan**: Strategy and technical plan before implementation.
   - **Implementation Details**: Code snippets with explanations for key files.

4. Workflow rules:
   - Update the breadcrumb **BEFORE** making any code changes.
   - **Get explicit approval** on the plan before implementation.
   - Update the breadcrumb **AFTER completing each significant change**.
   - Keep the breadcrumb as our single source of truth as it contains the most recent information.

5. Ask me to verify the plan with: "Are you happy with this implementation plan?" before proceeding with code changes.

6. Reference related breadcrumbs when a task builds on previous work.

7. Before concluding, ensure the breadcrumb file properly documents the entire process, including any course corrections or challenges encountered.

This practice creates a trail of decision points that document our thought process while building features in this solution, making pull
request review for the current change easier to follow as well.

### Plan Structure Guidelines

- When creating a plan, organize it into numbered phases (e.g., "Phase 1: Setup Dependencies").
- Break down each phase into specific tasks with numeric identifiers (e.g., "Task 1.1: Add Dependencies").
- Include a detailed checklist at the end of the document that maps to all phases and tasks.
- Mark tasks as `- [ ]` for pending tasks and `- [x]` for completed tasks.
- Start all planning tasks as unchecked, and update them to checked as implementation proceeds.
- Each planning task should have clear success criteria.
- End the plan with success criteria that define when the implementation is complete.
- Plans should start with writing Unit Tests first when possible, so we can use those to guide our implementation. Same for UI tests when it makes sense.
- If the domain knowledge has changed, update the related files in the `domain_knowledge` folder.
- If specifications have changed, update the related files in the `specifications` folder.

### Following Plans

- When coding you need to follow the plan phases and check off the tasks as they are completed.
- As you complete a task, update the plan and mark that task complete before you being the next task.
- Tasks that involved tests should not be marked complete until the tests pass.
- All code must be put under the `front_end` folder.
