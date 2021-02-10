from micropython import const

from trezor import ui
from trezor.messages import ButtonRequestType
from trezor.ui.container import Container
from trezor.ui.loader import LoaderDanger
from trezor.ui.qr import Qr
from trezor.utils import chunks

from ..components.common import break_path_to_lines
from ..components.common.confirm import is_confirmed
from ..components.tt.button import ButtonCancel, ButtonDefault
from ..components.tt.confirm import Confirm, HoldToConfirm
from ..components.tt.scroll import Paginated
from ..components.tt.text import Text
from ..constants.tt import (
    MONO_CHARS_PER_LINE,
    MONO_HEX_PER_LINE,
    QR_SIZE_THRESHOLD,
    QR_X,
    QR_Y,
    TEXT_MAX_LINES,
)
from .common import interact

if False:
    from typing import Any, Iterator, List, Sequence, Union, Optional, Awaitable

    from trezor import wire
    from trezor.messages.ButtonRequest import EnumTypeButtonRequestType


__all__ = (
    "confirm_action",
    "confirm_wipe",
    "confirm_reset_device",
    "confirm_backup",
    "confirm_path_warning",
    "show_address",
    "show_error",
    "show_pubkey",
    "show_success",
    "show_xpub",
    "show_warning",
    "confirm_output",
    "confirm_hex",
    "confirm_total",
    "confirm_joint_total",
    "confirm_metadata",
    "confirm_replacement",
    "confirm_modify_fee",
)


async def confirm_action(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    action: str = None,
    description: str = None,
    verb: Union[str, bytes, None] = Confirm.DEFAULT_CONFIRM,
    verb_cancel: Union[str, bytes, None] = Confirm.DEFAULT_CANCEL,
    hold: bool = False,
    icon: str = None,  # TODO cleanup @ redesign
    icon_color: int = None,  # TODO cleanup @ redesign
    reverse: bool = False,  # TODO cleanup @ redesign
    larger_vspace: bool = False,  # TODO cleanup @ redesign
    br_code: EnumTypeButtonRequestType = ButtonRequestType.Other,
    **kwargs: Any,
) -> bool:
    text = Text(
        title,
        icon if icon is not None else ui.ICON_DEFAULT,
        icon_color if icon_color is not None else ui.ORANGE_ICON,
        new_lines=False,
    )

    if reverse and description is not None:
        text.normal(description)
    elif action is not None:
        text.bold(action)

    if action is not None and description is not None:
        text.br()
        if larger_vspace:
            text.br_half()

    if reverse and action is not None:
        text.bold(action)
    elif description is not None:
        text.normal(description)

    cls = HoldToConfirm if hold else Confirm
    return is_confirmed(
        await interact(
            ctx,
            cls(text, confirm=verb, cancel=verb_cancel),
            br_type,
            br_code,
        )
    )


# TODO cleanup @ redesign
async def confirm_wipe(ctx: wire.GenericContext) -> bool:
    text = Text("Wipe device", ui.ICON_WIPE, ui.RED)
    text.normal("Do you really want to", "wipe the device?", "")
    text.bold("All data will be lost.")
    return is_confirmed(
        await interact(
            ctx,
            HoldToConfirm(text, confirm_style=ButtonCancel, loader_style=LoaderDanger),
            "wipe_device",
            ButtonRequestType.WipeDevice,
        )
    )


async def confirm_reset_device(ctx: wire.GenericContext, prompt: str) -> bool:
    text = Text("Create new wallet", ui.ICON_RESET, new_lines=False)
    text.bold(prompt)
    text.br()
    text.br_half()
    text.normal("By continuing you agree")
    text.br()
    text.normal("to")
    text.bold("https://trezor.io/tos")
    return is_confirmed(
        await interact(
            ctx,
            Confirm(text, major_confirm=True),
            "setup_device",
            ButtonRequestType.ResetDevice,
        )
    )


# TODO cleanup @ redesign
async def confirm_backup(ctx: wire.GenericContext) -> bool:
    text1 = Text("Success", ui.ICON_CONFIRM, ui.GREEN)
    text1.bold("New wallet created", "successfully!")
    text1.br_half()
    text1.normal("You should back up your", "new wallet right now.")

    text2 = Text("Warning", ui.ICON_WRONG, ui.RED)
    text2.bold("Are you sure you want", "to skip the backup?")
    text2.br_half()
    text2.normal("You can back up your", "Trezor once, at any time.")

    if is_confirmed(
        await interact(
            ctx,
            Confirm(text1, cancel="Skip", confirm="Back up", major_confirm=True),
            "backup_device",
            ButtonRequestType.ResetDevice,
        )
    ):
        return True

    confirmed = is_confirmed(
        await interact(
            ctx,
            Confirm(text2, cancel="Skip", confirm="Back up", major_confirm=True),
            "backup_device",
            ButtonRequestType.ResetDevice,
        )
    )
    return confirmed


async def confirm_path_warning(ctx: wire.GenericContext, path: str) -> bool:
    text = Text("Confirm path", ui.ICON_WRONG, ui.RED)
    text.normal("Path")
    text.mono(*break_path_to_lines(path, MONO_CHARS_PER_LINE))
    text.normal("is unknown.", "Are you sure?")
    return is_confirmed(
        await interact(
            ctx,
            Confirm(text),
            "path_warning",
            ButtonRequestType.UnknownDerivationPath,
        )
    )


def _show_qr(
    address: str,
    desc: str,
    cancel: str = "Address",
) -> Confirm:
    QR_COEF = const(4) if len(address) < QR_SIZE_THRESHOLD else const(3)
    qr = Qr(address, QR_X, QR_Y, QR_COEF)
    text = Text(desc, ui.ICON_RECEIVE, ui.GREEN)

    return Confirm(Container(qr, text), cancel=cancel, cancel_style=ButtonDefault)


def _split_address(address: str) -> Iterator[str]:
    return chunks(address, MONO_CHARS_PER_LINE)


def _hex_lines(hex_data: str, lines: int = TEXT_MAX_LINES) -> Iterator[str]:
    if len(hex_data) >= MONO_HEX_PER_LINE * lines:
        hex_data = hex_data[: (MONO_HEX_PER_LINE * lines - 3)] + "..."
    return chunks(hex_data, MONO_HEX_PER_LINE)


def _show_address(
    address: str,
    desc: str,
    network: str = None,
) -> Confirm:
    text = Text(desc, ui.ICON_RECEIVE, ui.GREEN)
    if network is not None:
        text.normal("%s network" % network)
    text.mono(*_split_address(address))

    return Confirm(text, cancel="QR", cancel_style=ButtonDefault)


def _show_xpub(xpub: str, desc: str, cancel: str) -> Paginated:
    pages: List[ui.Component] = []
    for lines in chunks(list(chunks(xpub, 16)), 5):
        text = Text(desc, ui.ICON_RECEIVE, ui.GREEN)
        text.mono(*lines)
        pages.append(text)

    content = Paginated(pages)

    content.pages[-1] = Confirm(
        content.pages[-1],
        cancel=cancel,
        cancel_style=ButtonDefault,
    )

    return content


async def show_xpub(
    ctx: wire.GenericContext, xpub: str, desc: str, cancel: str
) -> bool:
    return is_confirmed(
        await interact(
            ctx,
            _show_xpub(xpub, desc, cancel),
            "show_xpub",
            ButtonRequestType.PublicKey,
        )
    )


async def show_address(
    ctx: wire.GenericContext,
    address: str,
    address_qr: str = None,
    desc: str = "Confirm address",
    network: str = None,
    multisig_index: int = None,
    xpubs: Sequence[str] = [],
) -> None:
    is_multisig = len(xpubs) > 0
    while True:
        if is_confirmed(
            await interact(
                ctx,
                _show_address(address, desc, network),
                "show_address",
                ButtonRequestType.Address,
            )
        ):
            break
        if is_confirmed(
            await interact(
                ctx,
                _show_qr(
                    address if address_qr is None else address_qr,
                    desc,
                    cancel="XPUBs" if is_multisig else "Address",
                ),
                "show_qr",
                ButtonRequestType.Address,
            )
        ):
            break

        if is_multisig:
            for i, xpub in enumerate(xpubs):
                cancel = "Next" if i < len(xpubs) - 1 else "Address"
                desc = "XPUB #%d" % (i + 1)
                desc += " (yours)" if i == multisig_index else " (cosigner)"
                if is_confirmed(
                    await interact(
                        ctx,
                        _show_xpub(xpub, desc=desc, cancel=cancel),
                        "show_xpub",
                        ButtonRequestType.PublicKey,
                    )
                ):
                    return


def show_pubkey(
    ctx: wire.Context, pubkey: str, title: str = "Confirm public key"
) -> Awaitable[bool]:
    return confirm_hex(
        ctx,
        br_type="show_pubkey",
        title="Confirm public key",
        data=pubkey,
        br_code=ButtonRequestType.PublicKey,
        _receive=True,
    )


async def _show_modal(
    ctx: wire.GenericContext,
    br_type: str,
    br_code: EnumTypeButtonRequestType,
    header: str,
    subheader: Optional[str],
    content: str,
    button_confirm: Optional[str],
    button_cancel: Optional[str],
    icon: str,
    icon_color: int,
) -> bool:
    text = Text(header, icon, icon_color, new_lines=False)
    if subheader:
        text.bold(subheader)
        text.br()
        text.br_half()
    text.normal(content)
    return is_confirmed(
        await interact(
            ctx,
            Confirm(text, confirm=button_confirm, cancel=button_cancel),
            br_type,
            br_code,
        )
    )


def show_error(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
    header: str = "Error",
    subheader: Optional[str] = None,
    button: str = "Close",
) -> Awaitable[bool]:
    return _show_modal(
        ctx,
        br_type=br_type,
        br_code=ButtonRequestType.Other,
        header=header,
        subheader=subheader,
        content=content,
        button_confirm=None,
        button_cancel=button,
        icon=ui.ICON_WRONG,
        icon_color=ui.ORANGE_ICON,
    )


def show_warning(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
    subheader: Optional[str] = None,
    button: str = "Try again",
) -> Awaitable[bool]:
    return _show_modal(
        ctx,
        br_type=br_type,
        br_code=ButtonRequestType.Warning,
        header="Warning",
        subheader=subheader,
        content=content,
        button_confirm=button,
        button_cancel=None,
        icon=ui.ICON_WRONG,
        icon_color=ui.RED,
    )


def show_success(
    ctx: wire.GenericContext,
    br_type: str,
    content: str,
    subheader: Optional[str] = None,
    button: str = "Continue",
) -> Awaitable[bool]:
    return _show_modal(
        ctx,
        br_type=br_type,
        br_code=ButtonRequestType.Success,
        header="Success",
        subheader=subheader,
        content=content,
        button_confirm=button,
        button_cancel=None,
        icon=ui.ICON_CONFIRM,
        icon_color=ui.GREEN,
    )


async def confirm_output(
    ctx: wire.GenericContext,
    address: str,
    amount: str,
) -> bool:
    text = Text("Confirm sending", ui.ICON_SEND, ui.GREEN)
    text.normal(amount + " to")
    text.mono(*_split_address(address))
    return is_confirmed(
        await interact(
            ctx, Confirm(text), "confirm_output", ButtonRequestType.ConfirmOutput
        )
    )


# TODO: pagination for long keys
async def confirm_hex(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    data: str,
    br_code: EnumTypeButtonRequestType = ButtonRequestType.Other,
    _receive: bool = False,
) -> bool:
    text = Text(title, ui.ICON_RECEIVE if _receive else ui.ICON_SEND, ui.GREEN)
    text.mono(*_hex_lines(data))
    return is_confirmed(await interact(ctx, Confirm(text), br_type, br_code))


async def confirm_total(
    ctx: wire.GenericContext, total_amount: str, fee_amount: str
) -> bool:
    text = Text("Confirm transaction", ui.ICON_SEND, ui.GREEN)
    text.normal("Total amount:")
    text.bold(total_amount)
    text.normal("including fee:")
    text.bold(fee_amount)
    return is_confirmed(
        await interact(
            ctx, HoldToConfirm(text), "confirm_total", ButtonRequestType.SignTx
        )
    )


async def confirm_joint_total(
    ctx: wire.GenericContext, spending_amount: str, total_amount: str
) -> bool:
    text = Text("Joint transaction", ui.ICON_SEND, ui.GREEN)
    text.normal("You are contributing:")
    text.bold(spending_amount)
    text.normal("to the total amount:")
    text.bold(total_amount)
    return is_confirmed(
        await interact(
            ctx, HoldToConfirm(text), "confirm_joint_total", ButtonRequestType.SignTx
        )
    )


async def confirm_metadata(
    ctx: wire.GenericContext,
    br_type: str,
    title: str,
    content: str,
    param: Optional[str] = None,
    br_code: EnumTypeButtonRequestType = ButtonRequestType.SignTx,
) -> bool:
    text = Text(title, ui.ICON_SEND, ui.GREEN, new_lines=False)
    text.format_parametrized(content, param if param is not None else "")
    text.br()

    text.normal("Continue?")

    return is_confirmed(await interact(ctx, Confirm(text), br_type, br_code))


async def confirm_replacement(
    ctx: wire.GenericContext, description: str, txid: str
) -> bool:
    text = Text(description, ui.ICON_SEND, ui.GREEN)
    text.normal("Confirm transaction ID:")
    text.mono(*_hex_lines(txid, TEXT_MAX_LINES - 1))
    return is_confirmed(
        await interact(
            ctx, Confirm(text), "confirm_replacement", ButtonRequestType.SignTx
        )
    )


async def confirm_modify_fee(
    ctx: wire.GenericContext,
    sign: int,
    user_fee_change: str,
    total_fee_new: str,
) -> bool:
    text = Text("Fee modification", ui.ICON_SEND, ui.GREEN)
    if sign == 0:
        text.normal("Your fee did not change.")
    else:
        if sign < 0:
            text.normal("Decrease your fee by:")
        else:
            text.normal("Increase your fee by:")
        text.bold(user_fee_change)
    text.br_half()
    text.normal("Transaction fee:")
    text.bold(total_fee_new)
    return is_confirmed(
        await interact(ctx, HoldToConfirm(text), "modify_fee", ButtonRequestType.SignTx)
    )
