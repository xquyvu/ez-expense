        if existing_expenses.shape[0]:
            print("""Found existing expenses""")

            num_expenses_without_receipts = (existing_expenses["Receipts attached"] == "No").sum()

            if num_expenses_without_receipts:
                print(
                    dedent(
                        f"""
                        Found {num_expenses_without_receipts} expense(s) without receipts
                        attached.

                        1. Please find the line number of each expense without receipt by
                           looking at the `{EXPENSE_LINE_NUMBER_COLUMN}` column in the
                           spreadsheet saved at {existing_expenses_path.absolute()}. For
                           expenses not paid by corporate card, the line number can be in
                           increment of 2.

                        2. Gather the receipt file(s) you want to attach to the expense(s)
                           and put them in the {RECEIPTS_PATH.absolute()} directory.

                        3. Add the line number as prefix to the receipt file(s) that
                           corresponds to your expense. For example, if your expense with
                           line number `10` had 2 receipts files, `restaurant.jpg` and
                           `bar.jpg`, then rename the files to `10_restaurant.jpg` and
                           `10_bar.jpg`. """,
                    )
                )
                try:
                    input("Press <Enter> when you are done, or <Ctrl+C> to exit.")
                except (KeyboardInterrupt, EOFError):
                    print("\n🛑 User interrupted. Exiting gracefully...")
                    return

        # Now we add receipts to the expenses. Reload the existing expenses file because it may have been updated
        existing_expenses = pd.read_csv(existing_expenses_path)

        receipt_file_paths = list(RECEIPTS_PATH.glob("*"))

        mapped_receipt_files: dict[int, list[Path]] = {}
        unmapped_receipt_files = []

        for receipt_file_path in receipt_file_paths:
            try:
                expense_line_number = int(receipt_file_path.stem.split("_")[0])
                if expense_line_number in existing_expenses[EXPENSE_LINE_NUMBER_COLUMN].values:
                    mapped_receipt_files.setdefault(expense_line_number, []).append(
                        receipt_file_path
                    )
                else:
                    unmapped_receipt_files.append(receipt_file_path)
            except ValueError:
                unmapped_receipt_files.append(receipt_file_path)

        # Now join back to the pandas dataframe
        mapped_receipt_files_data = (
            pd.Series(mapped_receipt_files, name=RECEIPT_PATHS_COLUMN)
            .reset_index()
            .rename(columns={"index": EXPENSE_LINE_NUMBER_COLUMN})
        )

        existing_expenses_to_update = pd.merge(
            existing_expenses,
            mapped_receipt_files_data,
            on=EXPENSE_LINE_NUMBER_COLUMN,
            how="inner",
        )

        # Now, get all expense lines
        ids_of_expenses_to_update = existing_expenses_to_update["Created ID"].values
        expense_lines = page.get_by_role("textbox", name="Created ID", include_hidden=True).all()

        for expense_line in expense_lines:
            expense_line_id = int(expense_line.get_attribute("value"))

            if expense_line_id not in ids_of_expenses_to_update:
                continue

            # Select the expense line
            expense_line.dispatch_event("click")

            # Now we attach the receipts
            expense_details = existing_expenses_to_update.loc[
                existing_expenses_to_update["Created ID"] == expense_line_id
            ].squeeze()

            for receipt_file_path in expense_details[RECEIPT_PATHS_COLUMN]:
                page.click('a[name="EditReceipts"]')
                page.click('button[name="AddButton"]')

                # Upload receipt
                with page.expect_file_chooser() as file_chooser_info:
                    page.click('button[name="UploadControlBrowseButton"]')

                file_chooser = file_chooser_info.value
                file_chooser.set_files(receipt_file_path)

                page.click('button[name="UploadControlUploadButton"]')
                page.click('button[name="OkButtonAddNewTabPage"]')
                page.click('button[name="CloseButton"]')

                page.get_by_text("Save and continue", exact=True).click()


        existing_expenses_path = INPUT_DATA_PATH / "existing_expenses.csv"
        import_expense_my_expense(page, existing_expenses_path)
