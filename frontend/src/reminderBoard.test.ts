import { expect, it } from "vitest";

import { isReminderBoard } from "./localApi";

const board = () => ({
  schema_version: "cosmatter.project-reminder-board/v1",
  trust_status: "loopback_operational_reminders_not_schedule_or_execution_authorization",
  scheduler_status: "not_scheduled_local_observation_only",
  reminder_count: 1,
  reminders: [{ scope: "run", identifier: "run_1", kind: "external_dispatch_incomplete", status: "open", priority: "attention", stage: null, action_label: "verify_dispatch_before_recovery" }],
});

it("accepts the bounded, non-executing reminder projection", () => {
  expect(isReminderBoard(board())).toBe(true);
});

it("fails closed for unknown actions, duplicate reminders, or counter mismatches", () => {
  const unknown = board(); unknown.reminders[0].action_label = "launch_provider";
  expect(isReminderBoard(unknown)).toBe(false);
  const mismatched = board(); mismatched.reminders[0].action_label = "verify_provider_outcome_before_recovery";
  expect(isReminderBoard(mismatched)).toBe(false);
  const duplicate = board(); duplicate.reminders.push({ ...duplicate.reminders[0] }); duplicate.reminder_count = 2;
  expect(isReminderBoard(duplicate)).toBe(false);
  const countMismatch = board(); countMismatch.reminder_count = 2;
  expect(isReminderBoard(countMismatch)).toBe(false);
});
