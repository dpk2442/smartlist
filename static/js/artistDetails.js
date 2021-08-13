class ArtistDetails extends HTMLElement {
    constructor() {
        super();

        const shadowRoot = this.attachShadow({ mode: 'open' });
        shadowRoot.innerHTML = `
            <style>
                :host {
                    box-sizing: border-box;
                    border: 1px solid black;
                    border-radius: 0.5em;
                    padding: 0 1em;
                }
                #state-wrapper {
                    display: none;
                    background: #EEEEEE;
                    border-radius: 0.5em;
                    padding: 0.5em;
                }
                #spinner {
                    display: none;
                }
                .spinner {
                    width: 1ch;
                    height: 1ch;
                    border-radius: 50%;
                    border: 3px solid;
                    border-color: #666666 #666666 transparent transparent;
                    animation: spin 2s linear infinite;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                #last-updated {
                    font-size: 0.8em;
                }
            </style>
            <p id="state-wrapper">
                <span id="spinner" class="spinner"></span>
                <span id="state"></span>
            </p>
            <p>
                ${this.getAttribute('name')}
            </p>
            <p id="last-updated"></p>
        `;

        this._stateWrapper = shadowRoot.querySelector('#state-wrapper');
        this._spinner = shadowRoot.querySelector('#spinner');
        this._state = shadowRoot.querySelector('#state');
        this._lastUpdated = shadowRoot.querySelector('#last-updated');
    }

    _updateState() {
        switch (this.state) {
            case 'pending':
                this._stateWrapper.style.display = 'block';
                this._spinner.style.display = 'inline-block';
                this._state.textContent = 'Pending...';
                break;

            case 'syncing':
                this._stateWrapper.style.display = 'block';
                this._spinner.style.display = 'inline-block';
                this._state.textContent = 'Syncing...';
                break;

            case 'error':
                this._stateWrapper.style.display = 'block';
                this._spinner.style.display = 'none';
                this._state.textContent = `Error syncing: ${this.error}`;
                break;

            default:
                this._stateWrapper.style.display = 'none';
                this._spinner.style.display = 'none';
                this._state.textContent = '';
                break;
        }
    }

    _updateLastUpdated() {
        const lastUpdatedAttr = this.getAttribute('last-updated');
        if (!lastUpdatedAttr) {
            return;
        }
        this._lastUpdated.textContent = `Last Updated: ${new Date(lastUpdatedAttr).toLocaleString()}`;
    }

    static get observedAttributes() {
        return ['state', 'last-updated'];
    }

    attributeChangedCallback(name) {
        if (name === 'state') {
            this._updateState();
        } else if (name === 'last-updated') {
            this._updateLastUpdated();
        }
    }

    get id() {
        return this.getAttribute('id');
    }

    get state() {
        return this.getAttribute('state');
    }

    set state(val) {
        this.setAttribute('state', val);
    }

    set lastUpdated(val) {
        this.setAttribute('last-updated', val);
    }

    get error() {
        return this.getAttribute('error');
    }

    set error(val) {
        this.setAttribute('error', val);
    }
}

window.customElements.define('artist-details', ArtistDetails);
