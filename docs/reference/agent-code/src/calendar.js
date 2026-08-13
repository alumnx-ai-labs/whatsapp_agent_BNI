// calendar.js — calendar integration, stubbed for local testing.
// Swap this out for the real Google Calendar API (or Outlook) once credentials are available.
const CALENDAR_PROVIDER = process.env.CALENDAR_PROVIDER || 'stub';

async function bookMeeting({ title, startIso, durationMinutes, attendeePhone }) {
  if (CALENDAR_PROVIDER === 'stub') {
    const fakeId = `evt_${Math.random().toString(36).slice(2, 10)}`;
    console.log(`[calendar:stub] booking "${title}" at ${startIso} for ${durationMinutes}min (attendee ${attendeePhone})`);
    return {
      id: fakeId,
      title,
      startIso,
      durationMinutes,
      rsvpLink: `https://calendar.app.google/${fakeId}`,
    };
  }

  // --- Real Google Calendar integration goes here ---
  // const { google } = require('googleapis');
  // const calendar = google.calendar({ version: 'v3', auth: oauthClient });
  // const res = await calendar.events.insert({ calendarId: 'primary', requestBody: { ... } });
  // return { id: res.data.id, title, startIso, durationMinutes, rsvpLink: res.data.htmlLink };
  throw new Error(`CALENDAR_PROVIDER=${CALENDAR_PROVIDER} not implemented yet`);
}

module.exports = { bookMeeting };
