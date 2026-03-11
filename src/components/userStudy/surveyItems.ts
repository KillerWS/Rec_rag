import type { LikertItem, LikertSection } from './LikertSurvey';

const defaultLeft = 'Strongly Disagree';
const defaultRight = 'Strongly Agree';

/**
 * POST-TASK (after each block): Transparency + Decision Confidence + Cognitive Load
 * END-OF-STUDY (once, after all 4 blocks): Trust + Satisfaction + Manipulation Checks + Open-ended
 */

// ---------------------------
// A.1 Transparency (per task; primary; 5 items)
export const TRANSPARENCY_ITEMS: LikertItem[] = [
  { id: 'TRN_T1', question: 'I clearly understood why these items were recommended.', leftLabel: defaultLeft, rightLabel: defaultRight },
  // minimal fix: make it applicable to both systems
  { id: 'TRN_T2', question: 'The system helped me understand trade-offs among options (e.g., through explanations or visual information).', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T3', question: 'I could connect the evidence (e.g., review snippets) to the suggested items.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T4', question: 'The system’s rationale was transparent and traceable to me.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T5R', question: '(R) I felt unsure how the system arrived at its suggestions.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// optional Berlin wording (keep same TRN_T2 ID so scoring stays consistent)
export const TRANSPARENCY_ITEMS_BERLIN: LikertItem[] = [
  { id: 'TRN_T1', question: 'I clearly understood why these items were recommended.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T2', question: 'The system helped me understand trade-offs between price and distance to Berlin city center (e.g., via charts or explanations).', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T3', question: 'I could connect the evidence (e.g., review snippets) to the suggested items.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T4', question: 'The system’s rationale was transparent and traceable to me.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRN_T5R', question: '(R) I felt unsure how the system arrived at its suggestions.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.2 Decision Confidence (per task; primary; 5 items)
export const DECISION_CONFIDENCE_ITEMS: LikertItem[] = [
  { id: 'CONF_C1', question: 'I felt confident about my final choice.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CONF_C2', question: 'I was confident when narrowing down options.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CONF_C3', question: 'I had enough information to make a good decision.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CONF_C4R', question: '(R) I doubted whether I was selecting the right option.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CONF_C5', question: 'I could justify my choice to someone else.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.3 Cognitive Load (per task; secondary; 4 items)
export const COGNITIVE_LOAD_ITEMS: LikertItem[] = [
  { id: 'CL_L1', question: 'The information provided was easy to process.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CL_L2R', question: '(R) The interaction felt mentally demanding.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CL_L3', question: 'I did not feel overwhelmed by the amount of information.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'CL_L4', question: 'The pace and granularity of details were appropriate.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.4 Trust (end of study; secondary; 3 items)
export const TRUST_ITEMS: LikertItem[] = [
  { id: 'TRUST_R1', question: 'I trusted the system’s recommendations.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRUST_R2', question: 'The provided evidence/explanations felt reliable.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'TRUST_R3', question: 'I would rely on similar recommendations in the future.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.5 Satisfaction (end of study; secondary; 3 items)
export const SATISFACTION_ITEMS: LikertItem[] = [
  { id: 'SAT_S1', question: 'Overall, I am satisfied with my experience using the system.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'SAT_S2', question: 'The interaction matched my expectations.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'SAT_S3', question: 'I would use this system for a similar task.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.6 Manipulation Checks (end of study; 2 items; not part of main scales)
export const MANIPULATION_CHECK_ITEMS: LikertItem[] = [
  { id: 'MC_A1', question: 'The system adapted its questions and information in real time based on my inputs.', leftLabel: defaultLeft, rightLabel: defaultRight },
  { id: 'MC_A2', question: 'Visual information was updated dynamically during interaction, not just at the end.', leftLabel: defaultLeft, rightLabel: defaultRight },
];

// ---------------------------
// A.7 Open-ended prompts (end of study; 2 prompts)
export const OPEN_ENDED_PROMPTS: string[] = [
  'What helped you the most to make a decision? (OPEN_1)',
  'If you could change one thing about the system, what would it be? (OPEN_2)',
];

// ---------------------------
// Flattened sets
export const POST_TASK_QUESTIONS: LikertItem[] = [
  ...TRANSPARENCY_ITEMS,
  ...DECISION_CONFIDENCE_ITEMS,
  ...COGNITIVE_LOAD_ITEMS,
];

export const END_OF_STUDY_QUESTIONS: LikertItem[] = [
  ...TRUST_ITEMS,
  ...SATISFACTION_ITEMS,
  ...MANIPULATION_CHECK_ITEMS,
];

// ---------------------------
// Sectioned structure
export const POST_TASK_SECTIONS: LikertSection[] = [
  {
    title: 'Transparency',
    description: 'These questions refer to the system you just used in this task and ask how clearly you understood its reasoning.',
    items: TRANSPARENCY_ITEMS,
  },
  {
    title: 'Decision Confidence',
    description: 'These questions ask how confident you felt while making your decision in this task.',
    items: DECISION_CONFIDENCE_ITEMS,
  },
  {
    title: 'Cognitive Load (per task, short form)',
    description: 'These questions ask how mentally demanding the interaction felt in this task.',
    items: COGNITIVE_LOAD_ITEMS,
  },
];

export const END_OF_STUDY_SECTIONS: LikertSection[] = [
  {
    title: 'Trust (post-study only)',
    description: 'These questions ask about your overall trust in the system.',
    items: TRUST_ITEMS,
  },
  {
    title: 'Satisfaction (post-study only)',
    description: 'These questions ask about your overall satisfaction with the system.',
    items: SATISFACTION_ITEMS,
  },
  {
    title: 'Checks (post-study only)',
    description: 'These questions help us verify key system properties (not part of main scores).',
    items: MANIPULATION_CHECK_ITEMS,
  },
];