export function questionMatchesCourseOutcome(question, selectedNumber, outcomes) {
  if (!selectedNumber) return true;
  const outcomeNumber = question.co_number
    ?? outcomes.find((outcome) => String(outcome.id) === String(question.co_id))?.number
    ?? question.co_id;
  return String(outcomeNumber) === String(selectedNumber);
}
