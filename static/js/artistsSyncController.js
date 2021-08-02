function sleep(timeout) {
    return new Promise((resolve) => {
        setTimeout(resolve, timeout);
    });
}

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

        this._syncButton = shadowRoot.querySelector('#sync');
        this._syncButton.addEventListener('click', () => this._sync());

        this._detailsElements = Object.fromEntries(
            Array.prototype.slice.apply(this.querySelectorAll('artist-details')).map((el) => [el.id, el])
        );
    }

    async _sync() {
        this._syncButton.disabled = true;

        for (const el of Object.values(this._detailsElements)) {
            el.state = 'pending';
        }

        await sleep(1000);

        for (const id of Object.keys(this._detailsElements)) {
            this._detailsElements[id].state = 'syncing';
            await sleep(2000);
            this._detailsElements[id].state = '';
        }

        for (const el of Object.values(this._detailsElements)) {
            if (el.state) {
                el.error = 'No sync perfomed';
                el.state = 'error';
            }
        }

        this._syncButton.disabled = false;
    }
}

window.customElements.define('artists-sync-controller', ArtistsSyncController);
