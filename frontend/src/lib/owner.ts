// What this browser remembers about the links it made.
//
// The owner key is returned once by POST /shares and stored here; it is what
// separates the person who minted a link from anyone else holding it, and it
// is the only reason the share page can show an owner block at all. Losing it
// (a different browser, cleared storage) costs the ability to send mail for
// that share, not the link — which stays live until it expires.

const KEY = (token: string) => `share.owner-key.${token}`
const NAME = 'share.owner-name'
const FROM = 'share.from-account'

// Private browsing and blocked storage throw on access rather than returning
// null, and none of this is worth failing a page over.
function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* the share still works; only the owner controls are lost */
  }
}

export const ownerKey = (token: string) => read(KEY(token))
export const rememberOwnerKey = (token: string, key: string) => write(KEY(token), key)

/** The corrected display name, sent with the next POST /shares so the fix is
 *  made once rather than once per link. */
export const ownerName = () => read(NAME)
export const rememberOwnerName = (name: string) => write(NAME, name)

/** The mailbox this browser last sent from, so the choice is asked once. */
export const lastFrom = () => read(FROM)
export const rememberFrom = (accountId: string) => write(FROM, accountId)
