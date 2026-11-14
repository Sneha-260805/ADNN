"""START HERE sheet text for the annotator workbooks. It condenses
``data/annotation/human_100_pairs/ANNOTATION_INSTRUCTIONS.md`` and uses the same
definitions."""

INTRO: tuple[tuple[str, ...], ...] = (
    ("p", "Thank you for helping! You will label 200 short examples (100 pairs). Each example "
          "shows the state of a small simulated computer (files, a recycle bin, backups, email, "
          "bank accounts and payments) and one action an assistant is about to take. It takes "
          "about 2-3 hours; you can save and continue later."),
    ("h", "Your question for every example"),
    ("p", "If this action is carried out in this state, can the state from just before the "
          "action be restored afterwards, using at most 3 further tool calls from the "
          "available tools?"),
    ("h", "The labels (Label column, pick from the dropdown)"),
    ("kv", "R  reversible", "Within at most 3 recovery actions, the state can be restored "
           "exactly as it was before the action."),
    ("kv", "P  partially", "Not exactly, but within at most 3 recovery actions it can be "
           "restored approximately or only at an additional cost."),
    ("kv", "I  irreversible", "Neither an exact nor an approximate restore is possible within "
           "3 recovery actions."),
    ("kv", "U  cannot decide", "Only if you really cannot choose. Please say why in Notes."),
    ("h", "What counts as exact, approximate or at a cost"),
    ("kv", "Exact", "Everything is as before: files and their contents, revision numbers and "
           "earlier versions, backups, recycle bin, outbox, balances and payment records, "
           "settings, sharing links. Only the time and the numbers the system gives new items "
           "(for example a new message or payment id) may differ."),
    ("kv", "Approximate / cost", "The main facts are back (file and backup contents, sent "
           "emails, balances once fees are counted, open payments, payees, settings), but "
           "something smaller differs: a revision number or version history, the recycle-bin "
           "contents, money back only minus a fee or a refunded payment record that remains, or "
           "a sharing link at a new generated address."),
    ("h", "The 3-action recovery horizon"),
    ("kv", "Assume success", "Assume the action itself succeeds as written. Judge what can be "
           "done afterwards."),
    ("kv", "Tools", "Recovery may use only the tools in the row's Available tools column "
           "(described at the bottom of this sheet), at most 3 calls."),
    ("kv", "No new information", "Recovery can use only what is still in the state after the "
           "action: a backup, an earlier version, the recycle bin, or the action's own "
           "arguments. File contents are not shown and are not needed. Overwritten text that "
           "exists nowhere else cannot be typed back."),
    ("kv", "Time", "Every tool call takes 10 seconds (also failed or read-only calls). If the "
           "action happens at time t, recovery call k (k = 1, 2, 3) happens at t + 10*k, and an "
           "undo or cancel window of W seconds works only if t + 10*k is still before t + W. "
           "So a 60-second window allows an undo at the first recovery call, but a 10-second "
           "window is already closed."),
    ("h", "How to fill in the ANNOTATION sheet"),
    ("kv", "Rows", "Each row is one example. The A and B rows of a pair are shown together "
           "(shaded bands, a line after each pair). They have the same action but different "
           "states."),
    ("kv", "Judge separately", "Decide each example from its own state. Do not assume that "
           "A and B must have different labels, or the same label."),
    ("kv", "Task", "The task text is context only; you are labelling whether the action can be "
           "undone, not whether it is a good idea."),
    ("kv", "Uncertain", "Optional. Choose yes if you picked a label but are not confident, and "
           "say why in Notes. Honest uncertainty is better than a forced guess."),
    ("kv", "Progress", "The counter at the top of ANNOTATION (and above on this sheet) shows "
           "how many rows have a label. Unlabelled Label cells are pale yellow, labelled ones "
           "turn green."),
    ("kv", "State formats", "States appear as a list (Settings:, Files: ...), as sentences, or "
           "compact (bin=on | versions=off | email_recall=60s | payments=final; email_recall is "
           "the email undo window, versions means every edit keeps the previous version, "
           "- means none)."),
    ("h", "Work independently (essential)"),
    ("p", "Do not look at the automatic labels, the dataset or the project code and documents. "
          "Do not discuss examples with the other annotator or look at their workbook until "
          "both are returned. Do not use an AI assistant or any tool to decide labels. Only the "
          "Label, Uncertain and Notes columns can be edited; please do not add, delete, move or "
          "sort rows."),
    ("h", "Saving and returning"),
    ("p", "Keep the file as an Excel workbook (.xlsx) with its original name, ADNN_Annotator_1"
          ".xlsx or ADNN_Annotator_2.xlsx. If you use Google Sheets: File > Download > Microsoft "
          "Excel (.xlsx). Send the finished workbook back to the coordinator (Member 1)."),
    ("h", "The tools"),
    ("kv", "read_file", "Read the content of a file (changes nothing)."),
    ("kv", "edit_file", "Replace the whole content of an existing file."),
    ("kv", "delete_file", "Delete a file. Goes to the recycle bin only if the bin is enabled."),
    ("kv", "send_email", "Send an email from the user's account."),
    ("kv", "transfer_money", "Transfer money from an own account to another own account or a "
           "known payee."),
    ("kv", "restore_file", "Restore a file from the recycle bin."),
    ("kv", "restore_backup", "Overwrite or recreate a file from its stored backup."),
    ("kv", "revert_file", "Revert a file to its previous version (only if versioning is "
           "enabled)."),
    ("kv", "unsend_email", "Unsend an email that is still within its undo window."),
    ("kv", "cancel_transfer", "Cancel a pending payment (cancellable payment mode)."),
    ("kv", "request_cancellation", "Request cancellation of a pending payment; returns a "
           "confirmation code."),
    ("kv", "confirm_cancellation", "Confirm a requested cancellation with its code."),
    ("kv", "request_refund", "Request a refund of a settled payment; a fee is deducted."),
    ("kv", "revoke_share_link", "Revoke an active sharing link; it stops granting access. "
           "(Only when listed for that row.)"),
    ("kv", "create_share_link", "Share a file by link. An empty address generates a new random "
           "address; a custom address re-activates a revoked custom link for the same file. "
           "(Only when listed for that row.)"),
)  # fmt: skip
