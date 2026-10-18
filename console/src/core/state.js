// What the person is doing on the page, kept until it is reloaded: the answer picked or typed on each card before it
// is sent, the opened assistant, a new check waiting to be shown. Everything that is true of the project comes from
// the data layer (src/data), never from here.
export const S = {
  chosen: {},     // decision or question id -> the option picked, not sent yet
  own: {},        // id -> the answer typed in the person's own words
  ownOpen: {},    // id -> the own-words box is open
  sending: {},    // id -> its answer is on its way to the server
  assist: { open: false, ctxOff: null, draft: '' },
  newcheck: false, // a new check landed while the person reads Problems (PRB-11)
};
