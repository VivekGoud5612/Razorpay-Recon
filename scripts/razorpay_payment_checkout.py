from __future__ import annotations

import asyncio
import csv
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from recon.infrastructure.razorpay.gateway import RazorpayApiGateway


CHECKOUT_URL = "http://localhost:8000/scripts/razorpay_checkout.html"
BASE_PATH = Path("/home/vivek/Downloads/razorpay_recon_50_scenarios")

TEST_CARD = "4100280000001007"
TEST_EXPIRY = "12/30"
TEST_CVV = "123"
TEST_MOBILE = "9000090000"


def load_orders(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


async def find_frame_with_selector(page, selector: str):
    for frame in page.frames:
        if await frame.locator(selector).count() > 0:
            return frame
    return None


async def run_checkout(
    page,
    gateway: RazorpayApiGateway,
    order: dict,
    scenario: str,
) -> None:
    order_id = order["razorpay_order_id"]

    if not order_id or not order_id.startswith("order_"):
        print(f"Skipping {order['merchant_order_id']}: invalid Razorpay order ID")
        return

    payments = await gateway.fetch_order_payments(order_id)

    if any(payment.status == "captured" for payment in payments):
        print(f"Skipping {order['merchant_order_id']}: payment already captured")
        return

    amount = int(float(order["amount"]) * 100)

    params = urlencode({
        "order_id": order_id,
        "amount": amount,
        "currency": order["currency"],
        "scenario": scenario,
    })

    await page.goto(f"{CHECKOUT_URL}?{params}")
    await page.locator("#pay-button").click()
    await page.wait_for_timeout(2000)

    checkout_frame = page.frame(
        url=re.compile(r"https://api\.razorpay\.com/v1/checkout/public")
    )

    if checkout_frame is None:
        raise RuntimeError("Razorpay Checkout frame not found")

    mobile = checkout_frame.get_by_placeholder("Mobile number")

    if await mobile.is_visible():
        await mobile.fill(TEST_MOBILE)

        await checkout_frame.get_by_test_id(
            "contact-overlay-container"
        ).get_by_role(
            "button",
            name="Continue",
        ).click()

        await checkout_frame.wait_for_timeout(1000)

    card_frame = await find_frame_with_selector(
        page,
        'input[placeholder*="Card Number"]',
    )

    if card_frame is None:
        raise RuntimeError("Razorpay card input frame not found")

    await card_frame.locator(
        'input[placeholder*="Card Number"]'
    ).fill(TEST_CARD)

    await card_frame.locator(
        'input[placeholder*="MM / YY"]'
    ).fill(TEST_EXPIRY)

    await card_frame.locator(
        'input[placeholder*="CVV"]'
    ).fill(TEST_CVV)

    context = page.context

    async with context.expect_page() as page_info:
        await card_frame.get_by_role(
            "button",
            name="Continue",
        ).click()

    bank_page = await page_info.value
    await bank_page.wait_for_load_state()

    print(
        f"Mock bank opened: "
        f"{order['merchant_order_id']} -> {bank_page.url}"
    )

    await bank_page.get_by_role(
        "button",
        name="Success",
    ).click()

    print(
        f"Test payment success selected: "
        f"{order['merchant_order_id']}"
    )

    await bank_page.wait_for_timeout(3000)

    payments = await gateway.fetch_order_payments(order_id)

    captured_payment = next(
        (
            payment
            for payment in payments
            if payment.status == "captured"
        ),
        None,
    )

    if captured_payment is None:
        print(
            f"Payment not captured: "
            f"{order['merchant_order_id']} -> {order_id}"
        )
        print(
            f"Payment states: "
            f"{[payment.status for payment in payments]}"
        )
        return

    print(
        f"Payment captured: "
        f"{order['merchant_order_id']} -> {order_id}"
    )


async def process_scenario(
    gateway: RazorpayApiGateway,
    scenario_path: Path,
) -> None:
    orders = load_orders(
        scenario_path / "merchant_faulty" / "merchant_orders.csv"
    )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
        )

        try:
            page = await browser.new_page()

            for order in orders:
                try:
                    await run_checkout(
                        page,
                        gateway,
                        order,
                        scenario_path.name,
                    )
                except Exception as exc:
                    print(
                        f"Checkout failed for "
                        f"{order['merchant_order_id']}: {exc}"
                    )

        finally:
            await browser.close()


async def main() -> None:
    load_dotenv()

    gateway = RazorpayApiGateway(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )

    if len(sys.argv) > 1:
        scenario_paths = [Path(sys.argv[1])]
    else:
        scenario_paths = [
            path
            for path in sorted(BASE_PATH.iterdir())
            if path.is_dir()
            and (path / "razorpay.json").exists()
        ]

    for scenario_path in scenario_paths:
        print(f"\n=== {scenario_path.name} ===")

        await process_scenario(
            gateway,
            scenario_path,
        )


if __name__ == "__main__":
    asyncio.run(main())