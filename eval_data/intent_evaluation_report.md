# Banking77 Intent Coverage Evaluation Report

**Date**: 2026-09-25
**Dataset**: Banking77 Test Set (3080 samples, 77 intents)

## 1. Coverage Summary

| Metric | Value |
|--------|-------|
| Total Banking77 intents | 77 |
| Intents covered by our system | 46 |
| Intents out of scope | 31 |
| **Coverage rate** | **59.7%** |
| Test samples mapping to covered intents | 1800 / 3080 |
| Chinese query test accuracy | 90.9% (60/66) |

## 2. Intent Mapping Table

| Our System Intent | Banking77 Categories Mapped | Test Samples |
|-------------------|------------------------------|--------------|
| `balance_query` | `balance_not_updated_after_bank_transfer`, `balance_not_updated_after_cheque_or_cash_deposit` | 80 |
| `bill_analysis` | `Refund_not_showing_up`, `card_payment_fee_charged`, `card_payment_not_recognised`, `cash_withdrawal_charge`, `cash_withdrawal_not_recognised`, `extra_charge_on_statement`, `pending_card_payment`, `pending_cash_withdrawal`, `request_refund`, `transaction_charged_twice`, `wrong_amount_of_cash_received` | 440 |
| `card_activate` | `activate_my_card` | 40 |
| `card_apply` | `get_disposable_virtual_card`, `get_physical_card`, `getting_virtual_card`, `order_physical_card` | 160 |
| `card_limit` | `disposable_card_limits` | 40 |
| `card_query` | `card_about_to_expire`, `card_acceptance`, `card_arrival`, `card_delivery_estimate`, `card_linking`, `contactless_not_working`, `getting_spare_card`, `supported_cards_and_currencies`, `virtual_card_not_working`, `visa_or_mastercard` | 400 |
| `report_loss` | `card_not_working`, `card_swallowed`, `compromised_card`, `lost_or_stolen_card`, `lost_or_stolen_phone` | 200 |
| `subscription_query` | `direct_debit_payment_not_recognised` | 40 |
| `transfer` | `beneficiary_not_allowed`, `cancel_transfer`, `declined_transfer`, `failed_transfer`, `pending_transfer`, `receiving_money`, `reverted_card_payment`, `transfer_fee_charged`, `transfer_into_account`, `transfer_not_received_by_recipient`, `transfer_timing` | 400 |

## 3. Intent Detection Accuracy (Chinese Query Test)

| Intent | Queries Tested | Correct | Accuracy |
|--------|---------------|---------|----------|
| `aa_split` | 3 | 3 | 100% |
| `abort` | 3 | 3 | 100% |
| `balance_query` | 5 | 5 | 100% |
| `bill_analysis` | 5 | 5 | 100% |
| `bill_yearly` | 3 | 3 | 100% |
| `birthday_plan` | 3 | 3 | 100% |
| `help` | 3 | 3 | 100% |
| `human_takeover` | 3 | 3 | 100% |
| `investment_purchase` | 3 | 3 | 100% |
| `investment_query` | 4 | 3 | 75% |
| `investment_redeem` | 2 | 2 | 100% |
| `my_investments` | 2 | 1 | 50% |
| `report_loss` | 5 | 2 | 40% |
| `risk_assessment` | 2 | 2 | 100% |
| `scheduled_query` | 2 | 1 | 50% |
| `scheduled_transfer` | 3 | 3 | 100% |
| `subscription_cancel` | 5 | 5 | 100% |
| `subscription_query` | 5 | 5 | 100% |
| `transfer` | 5 | 5 | 100% |
| **Overall** | **66** | **60** | **90.9%** |

## 4. Uncovered Intents (Out of Scope)

The following 31 Banking77 intents are not covered by our system:

- `age_limit`
- `apple_pay_or_google_pay`
- `atm_support`
- `automatic_top_up`
- `card_payment_wrong_exchange_rate`
- `change_pin`
- `country_support`
- `declined_card_payment`
- `declined_cash_withdrawal`
- `edit_personal_details`
- `exchange_charge`
- `exchange_rate`
- `exchange_via_app`
- `fiat_currency_support`
- `passcode_forgotten`
- `pending_top_up`
- `pin_blocked`
- `terminate_account`
- `top_up_by_bank_transfer_charge`
- `top_up_by_card_charge`
- `top_up_by_cash_or_cheque`
- `top_up_failed`
- `top_up_limits`
- `top_up_reverted`
- `topping_up_by_card`
- `unable_to_verify_identity`
- `verify_my_identity`
- `verify_source_of_funds`
- `verify_top_up`
- `why_verify_identity`
- `wrong_exchange_rate_for_cash_withdrawal`

**Total out-of-scope test samples**: 1280 / 3080

## 5. Recommendations

### High Priority (Frequent in Banking77)
These uncovered categories have many test samples and could be considered for future expansion:
- `exchange_rate` (40 test samples)
- `card_payment_wrong_exchange_rate` (40 test samples)
- `fiat_currency_support` (40 test samples)
- `automatic_top_up` (40 test samples)
- `exchange_via_app` (40 test samples)
- `age_limit` (40 test samples)
- `pin_blocked` (40 test samples)
- `top_up_by_bank_transfer_charge` (40 test samples)
- `pending_top_up` (40 test samples)
- `top_up_limits` (40 test samples)

### Medium Priority
- Card-related operations (activate, delivery, linking) — common in real banking but out of MVP scope
- Top-up operations — relevant for digital wallet scenarios
- Exchange rate / currency — important for international banking
- Identity verification — security-critical, could integrate with our MFA flow

### Strengths of Current System
- Covers **46/77** Banking77 intents (59.7%)
- Strong coverage of transfer, balance, bill analysis, and card loss scenarios
- Chinese intent detection accuracy is high for covered intents
- Unique capabilities beyond Banking77: scheduled transfers, AA split, birthday planning, investment operations

### Gap Analysis
- Banking77 focuses heavily on card operations (physical/virtual card lifecycle) — our system focuses on transaction/agent workflows
- Banking77 has no coverage for: scheduled payments, bill splitting, goal-based planning, investment operations
- Our system's strength is in **actionable banking agent workflows**, not card customer support

---
*Report generated by `eval_data/evaluate_intent.py`*