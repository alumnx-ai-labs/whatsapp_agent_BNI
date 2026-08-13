// session.js — in-memory per-phone-number conversation state.
// Swap this for Redis/DB in production; the state machine only needs get/set/clear.

const STATES = {
  START: 'START',
  AWAITING_NAME: 'AWAITING_NAME',                 // new user: waiting for name + business name
  ASK_PAIN_POINT: 'ASK_PAIN_POINT',                // asked, waiting for user's pain point
  AWAITING_ELABORATION: 'AWAITING_ELABORATION',    // validation failed once, waiting for a clearer answer
  ASK_MEETING: 'ASK_MEETING',                      // pain point valid, asked "can you spare 30 min?"
  PROPOSE_TIME: 'PROPOSE_TIME',                    // waiting for user's availability
  CONFIRM_TIME: 'CONFIRM_TIME',                    // checking/confirming proposed time
  DONE: 'DONE',
};

const _sessions = new Map();

function getSession(phone) {
  if (!_sessions.has(phone)) {
    _sessions.set(phone, {
      phone,
      state: STATES.START,
      elaborationAttempts: 0,
      customer: null,
      pendingPainPoint: null,
      validatedPainPoint: null,
      proposedTime: null,
    });
  }
  return _sessions.get(phone);
}

function setState(phone, state) {
  getSession(phone).state = state;
}

function resetSession(phone) {
  _sessions.delete(phone);
}

module.exports = { STATES, getSession, setState, resetSession };
