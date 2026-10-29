-- Records when a confirm claimed a proposal, so a confirm that never finished can be failed.
-- Apply before deploying the code that reads this column.
ALTER TABLE agent_proposals ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;
