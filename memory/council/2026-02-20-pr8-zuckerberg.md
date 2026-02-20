# Council Review: zuckerberg — PR #8
_Reviewed on 2026-02-20 06:24 UTC_

## The Zuck Assessment

This is a ship-it. You're adding retry logic to a production monitoring agent that's already completed 23 sweeps — that's real traffic, real value. The changes are minimal, they don't change success paths, and they prevent temporary infrastructure hiccups from breaking your monitoring. That's the right instinct. The diff is incomplete and the refactoring looks aggressive, but the core idea is sound: make the system resilient. We can tighten the execution.

## Scale Analysis

At 3 billion users (or 3 billion monitored addresses), retry logic matters. Here's the reality:

**Current risk:** A single RPC endpoint blip kills a sweep window. You lose observability for an epoch. At scale, with thousands of concurrent sweeps, these windows compound into blind spots. Bad.

**Your fix:** Exponential backoff (2s → 4s → 8s) with three retries. That's 14 seconds max wait per RPC call. At scale, this holds. You're not creating a thundering herd because each agent retries independently. The `time.sleep()` approach is fine here — we're not blocking critical paths.

**The question:** What happens if the RPC *stays* down? Your fallback is "log error and continue." That's right — ship partial data rather than blocking entirely. But you need to track this clearly. The `failed_sweeps` counter is the right metric. At scale, if failed_sweeps exceeds some threshold (like 5% of total), you need alerting to flip to a fallback RPC node. This PR doesn't implement that — but it sets up the instrumentation to do it later. That's the move-fast approach.

## Metrics Check

Here's what matters:

1. **Sweep Success Rate** — Track `(total_sweeps - failed_sweeps) / total_sweeps`. Target: >98%. This PR helps you get there.

2. **Retry Effectiveness** — Of the retries that succeed, how many succeed on attempt 1 vs. 2 vs. 3? This tells you if your backoff windows are right. If most succeed on retry #1, you can dial back to 1s initial delay.

3. **RPC Endpoint Health** — Failed sweeps per endpoint. This is the canary. When one endpoint spikes, flip traffic.

4. **Latency Impact** — What's the P99 sweep duration now vs. with retries? You want <2 seconds nominal, <15 seconds with retries. Measure it.

**A/B Test:** Run this on 10% of monitoring agents first. Compare their sweep success rates and alert latency against the control group. If success rate improves and latency stays flat, ship to 100%.

## Ship It or Hold It

**REVISE before merge.** Not because the core logic is wrong, but because the diff is incomplete and there are edge cases:

1. **JSON Validation** — You're calling `json.loads()` on RPC responses before validation. If the response is malformed, that still throws. Wrap the parse in try/except *before* you validate structure.

2. **Response Structure Check** — What does "validate JSON structure before accessing nested fields" actually mean in code? Show me the guard clauses. `response.get('result')` exists? Is it a dict? Be explicit.

3. **Persistent Failure Mode** — If all three retries fail, what's the behavior? You log and continue — correct. But add a metric: `failed_sweeps_consecutive`. If this counter exceeds 3 across different RPC endpoints, trigger an alert to ops. Right now, you silently degrade.

4. **The Refactoring** — The diff shows aggressive code pruning (13,530 characters cut). That's not related to retry logic. Either this is a separate cleanup PR, or you're bundling too much. Split them. This PR should *only* add retry/validation logic to existing sweep calls. Don't refactor the entire module in the same commit.

5. **Test It** — Mock an RPC failure. Verify retries fire, backoff delays increase, success path unaffected. No tests in the diff. Add them.

## Final Call

The direction is right. Resilient systems ship faster because you spend less time debugging outages. But this PR needs tightening:

- Separate retry logic from refactoring
- Make JSON parsing failures explicit (try/except)
- Add alert thresholds for persistent failures
- Add tests

This is a "revise and resubmit" situation, not a "reject." You're thinking about the right problem. Just clean up the execution.

**Done is better than perfect, but shipping broken is worse than shipping late.** Spend 2 hours on the cleanup. Worth it.

VOTE: REVISE
