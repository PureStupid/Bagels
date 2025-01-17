from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import (
    Input,
    Label,
)

from bagels.components.autocomplete import AutoComplete, Dropdown, DropdownItem
from bagels.components.fields import Fields
from bagels.config import CONFIG
from bagels.modals.input import InputModal
from bagels.managers.accounts import get_all_accounts_with_balance
from bagels.managers.persons import create_person, get_all_persons
from bagels.forms.form import Form, Option
from bagels.forms.record_forms import RecordForm
from bagels.utils.validation import validateForm
from bagels.modals.base_widget import ModalContainer


class RecordModal(InputModal):

    isEditing = False

    BINDINGS = [
        Binding(
            CONFIG.hotkeys.record_modal.new_split,
            "add_split",
            "Add split",
            priority=True,
        ),
        Binding(
            CONFIG.hotkeys.record_modal.new_paid_split,
            "add_paid_split",
            "Add paid split",
            priority=True,
        ),
        Binding(
            CONFIG.hotkeys.record_modal.delete_last_split,
            "delete_last_split",
            "Delete last split",
            priority=True,
        ),
    ]

    def __init__(
        self,
        title: str,
        form: Form = Form(),
        splitForm: Form = Form(),
        isEditing: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(title, form, *args, **kwargs)
        self.record_form = RecordForm()
        self.splitForm = splitForm
        self.isEditing = isEditing
        if isEditing:
            self._bindings.key_to_bindings.clear()
            self.refresh_bindings()
        self.splitFormOneLength = len(self.record_form.get_split_form(0, False))
        self.splitCount = int(len(splitForm) / self.splitFormOneLength)
        self.persons = get_all_persons()
        self.accounts = get_all_accounts_with_balance()
        self.total_amount = 0
        self.split_total = Label("", id="split-total")

    def on_mount(self):
        self._update_split_total()
        if self.splitCount > 0:
            self._update_split_total_visibility(True)

    # -------------- Helpers ------------- #

    def _get_splits_from_result(self, resultForm: dict):
        splits = []
        for i in range(0, self.splitCount):
            splits.append(
                {
                    "personId": resultForm[f"personId-{i}"],
                    "amount": resultForm[f"amount-{i}"],
                    "isPaid": resultForm[f"isPaid-{i}"],
                    "accountId": resultForm[f"accountId-{i}"],
                    "paidDate": resultForm[f"paidDate-{i}"],
                }
            )
        return splits

    def _update_split_total(self, update_new: bool = True):
        my_amount = self.query_one("#field-amount").value
        total = float(my_amount) if my_amount else 0
        if update_new:
            for i in range(0, self.splitCount):
                amount = self.query_one(f"#field-amount-{i}").value
                total += float(amount) if amount else 0
        self.total_amount = total
        if self.splitCount > 0:
            self.split_total.update(
                f"Total amount: [bold yellow]{total:.2f}[/bold yellow]"
            )

    def _get_split_widget(self, index: int, fields: Form, isPaid: bool):
        widget = Container(Fields(fields), id=f"split-{index}", classes="split")
        widget.border_title = "> Paid split <" if isPaid else "> Split <"
        return widget

    def _get_init_split_widgets(self):
        widgets = []
        for i in range(0, self.splitCount):
            oneSplitForm = Form(
                fields=self.splitForm.fields[
                    i * self.splitFormOneLength : (i + 1) * self.splitFormOneLength
                ]
            )
            # Find the isPaid field in the form fields for this split
            isPaid = False
            for field in oneSplitForm.fields:
                if field.key == f"isPaid-{i}":
                    isPaid = field.default_value
                    break
            widgets.append(self._get_split_widget(i, oneSplitForm, isPaid))
        return widgets

    def _update_split_total_visibility(self, mount: bool):
        if mount:
            self.query_one(".container").mount(self.split_total)
        else:
            self.split_total.remove()

    def _update_errors(self, errors: dict):
        previousErrors = self.query(".error")
        for error in previousErrors:
            error.remove()
        for key, value in errors.items():
            field = self.query_one(f"#row-field-{key}")
            field.mount(Label(value, classes="error"))

    def on_auto_complete_created(self, event: AutoComplete.Created) -> None:
        name = event.item.create_option_text
        person = create_person({"name": name})
        for field in self.splitForm.fields:
            if field.key.startswith("personId"):
                field.options.items.append(Option(text=person.name, value=person.id))
        # update all person dropdowns with the new person
        for i in range(0, self.splitCount):
            dropdown: Dropdown = self.query_one(f"#dropdown-personId-{i}")
            dropdown.items.append(DropdownItem(person.name, "", ""))
        # set heldValue for the AutoComplete's input
        event.input.heldValue = person.id

    # def on_auto

    # ------------- Callbacks ------------ #

    def on_input_changed(self, event: Input.Changed):
        if event.input.id.startswith("field-amount"):
            self._update_split_total()

    def action_add_paid_split(self):
        self.action_add_split(paid=True)

    def action_add_split(self, paid: bool = False):
        splits_container = self.query_one("#splits-container", Container)
        current_split_index = self.splitCount
        new_split_form = self.record_form.get_split_form(current_split_index, paid)
        for field in new_split_form.fields:
            self.splitForm.fields.append(field)
        splits_container.mount(
            self._get_split_widget(current_split_index, new_split_form, paid)
        )
        # Use call_after_refresh to ensure the mount is complete
        splits_container.call_after_refresh(
            lambda: self.query_one(f"#field-personId-{current_split_index}").focus()
        )
        self.splitCount += 1
        if self.splitCount == 1:
            self._update_split_total_visibility(True)
            self._update_split_total(update_new=False)

    def action_delete_last_split(self):
        if self.splitCount > 0:
            self.query_one(f"#split-{self.splitCount - 1}").remove()
            self.query_one(
                f"#dropdown-personId-{self.splitCount - 1}"
            ).remove()  # idk why this is needed
            for i in range(self.splitFormOneLength):
                self.splitForm.fields.pop()
            self.splitCount -= 1
            if self.splitCount == 0:
                self._update_split_total_visibility(False)

    def action_submit(self):
        # We set the amount field to the total amount for the form to read the value
        input: Input = self.query_one("#field-amount")
        input.__setattr__("heldValue", str(self.total_amount))

        resultRecordForm, errors, isValid = validateForm(self, self.form)
        resultSplitForm, errorsSplit, isValidSplit = validateForm(self, self.splitForm)
        if isValid and isValidSplit:
            resultSplits = self._get_splits_from_result(resultSplitForm)
            self.dismiss({"record": resultRecordForm, "splits": resultSplits})
            return
        self._update_errors({**errors, **errorsSplit})
        # Remove the custom value we set for the field if not valid
        input.__setattr__("heldValue", None)

    # -------------- Compose ------------- #

    def compose(self) -> ComposeResult:
        yield ModalContainer(
            Fields(self.form),
            Container(*self._get_init_split_widgets(), id="splits-container"),
        )
