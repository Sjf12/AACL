// AACL Client SDK (Section 6.1 of the paper)
// Non-trusted convenience layer only

const AACL_SDK = {
    async issueGrammar(intent, businessParams = {}) {
        console.log(`[AACL SDK] Issuing grammar for intent: ${intent}`);

        // Send amount + recipient at issuance so server can lock them into the grammar.
        // Any modification after this point will mismatch the locked values.
        const res = await fetch(`/aacl/issue/${intent}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(businessParams)
        });
        
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            console.error('[AACL SDK] Grammar issuance failed:', err);
            throw new Error(err.error || 'Grammar issuance failed');
        }
        
        const data = await res.json();
        console.log('[AACL SDK] Grammar issued successfully:', data.grammar_id);
        return data;
    },

    buildRequest(grammar, businessParams) {
        console.log('[AACL SDK] Building request with grammar:', grammar.grammar_id);
        
        const payload = {
            grammar_id: grammar.grammar_id,
            intent: grammar.intent,
            entropy: grammar.entropy
        };
        
        grammar.required_keys.forEach(key => {
            if (!(key in businessParams)) {
                throw new Error(`Missing required parameter: ${key}`);
            }
            payload[key] = businessParams[key];
        });
        
        return payload;
    },

    async submit(intent, businessParams, endpoint = '/transfer') {
        try {
            const grammar = await this.issueGrammar(intent, businessParams);
            const payload = this.buildRequest(grammar, businessParams);
            
            console.log('[AACL SDK] Submitting payload:', payload);
            
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                console.error('[AACL SDK] Submission failed:', err);
                return err;  // Return error object for UI
            }
            
            return await res.json();
        } catch (e) {
            console.error('[AACL SDK] Exception:', e);
            return { error: e.message };
        }
    }
};

window.AACL_SDK = AACL_SDK;