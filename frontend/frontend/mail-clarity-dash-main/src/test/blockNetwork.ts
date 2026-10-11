// Tests never reach a real server. A request still in flight when its test (and its fetch stub) has
// ended would otherwise hit a backend running on this machine, and its answer, or the session
// refresh a 401 sets off, would land in the next test. vi.unstubAllGlobals restores this, not the
// real fetch, because it is the value in place when each test stubs fetch.
globalThis.fetch = () => Promise.reject(new TypeError("a test reached the network"));
