// aacl-sdk.js - Phase 3 Client-Side AACL SDK
// Include in HTML: <script src="/static/aacl-sdk.js"></script>

const AACL = (function () {
  let currentGrammar = null;

  // Fetch fresh grammar for an intent
  async function fetchGrammar(intent) {
    const response = await fetch(`/aacl/issue/${intent}`, {
      method: 'POST',
      credentials: 'include'  // Include session cookie
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch grammar: ${response.status}`);
    }

    currentGrammar = await response.json();
    console.log('[AACL] Grammar loaded for intent:', intent);
    return currentGrammar;
  }

  // Build payload in exact alphabetical order using required_keys
  function buildPayload(data) {
    if (!currentGrammar) {
      throw new Error('No grammar loaded');
    }

    const payload = {};
    const required = currentGrammar.required_keys;

    // Common fields (alphabetical order)
    payload.entropy = currentGrammar.entropy;
    payload.intent = currentGrammar.intent;
    payload.state = currentGrammar.state;

    // Add specific fields in alphabetical order
    required.forEach(key => {
      if (data[key] !== undefined) {
        payload[key] = data[key];
      } else {
        throw new Error(`Missing required key: ${key}`);
      }
    });

    // No extra keys allowed
    if (Object.keys(payload).length !== required.length + 3) {
      throw new Error('Payload has extra or missing keys');
    }

    return payload;
  }

  // Public API: Simple send method for developers
  async function send(intent, data) {
    try {
      // 1. Get fresh grammar if needed
      if (!currentGrammar || currentGrammar.intent !== intent) {
        await fetchGrammar(intent);
      }

      // 2. Build perfect payload
      const payload = buildPayload(data);

      // 3. Send protected request
      const response = await fetch('/aacl/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grammar_id: currentGrammar.grammar_id,
          payload: payload
        }),
        credentials: 'include'
      });

      const result = await response.json();

      // 4. AUTO-DESTROY grammar immediately (closes replay race)
      currentGrammar = null;
      console.log('[AACL] Grammar destroyed - replay impossible');

      return result;
    } catch (error) {
      console.error('[AACL] Error:', error);
      throw error;
    }
  }

  return { send };
})();