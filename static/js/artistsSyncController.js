class ArtistsSyncController extends HTMLElement {
    constructor() {
        super();

        const shadowRoot = this.attachShadow({ mode: 'open' });
        shadowRoot.innerHTML = `
            <p>
                <button id="sync">Sync Playlists</button>
            </p>
            <slot></slot>
        `;

        this._csrfToken = this.getAttribute('csrf-token');
        this._syncUrl = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        this._syncUrl += window.location.host + this.getAttribute('sync-url');

        this._syncButton = shadowRoot.querySelector('#sync');
        this._syncButton.addEventListener('click', () => this._sync());

        this._detailsElements = Object.fromEntries(
            Array.prototype.slice.apply(this.querySelectorAll('artist-details')).map((el) => [el.id, el])
        );
    }

    _sync() {
        this._syncButton.disabled = true;

        const ws = new WebSocket(this._syncUrl);
        ws.onopen = () => {
            ws.send(
                JSON.stringify({
                    type: 'csrf',
                    csrfToken: this._csrfToken,
                })
            );
        };
        ws.onmessage = (ev) => {
            const msg = JSON.parse(ev.data);
            switch (msg.type) {
                case 'start':
                    for (const el of Object.values(this._detailsElements)) {
                        el.state = 'pending';
                    }
                    break;

                case 'artistStart':
                    this._detailsElements[msg.artistId].state = 'syncing';
                    break;

                case 'artistError':
                    this._detailsElements[msg.artistId].error = msg.error;
                    this._detailsElements[msg.artistId].state = 'error';
                    break;

                case 'artistComplete':
                    this._detailsElements[msg.artistId].state = '';
                    this._detailsElements[msg.artistId].lastUpdated = msg.lastUpdated;
                    break;
            }
        };
        ws.onclose = () => {
            for (const el of Object.values(this._detailsElements)) {
                if (el.state && el.state !== 'error') {
                    el.error = 'No sync perfomed';
                    el.state = 'error';
                }
            }

            this._syncButton.disabled = false;
        };
    }
}

window.customElements.define('artists-sync-controller', ArtistsSyncController);
