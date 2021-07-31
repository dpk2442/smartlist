class ArtistsEditForm extends HTMLElement {
    constructor() {
        super();

        const shadowRoot = this.attachShadow({ mode: 'open' });
        shadowRoot.innerHTML = `
            <slot></slot>
            <p>
                <input type="button" id="save" value="Save" disabled>
                <input type="button" id="reset" value="Reset" disabled>
            </p>
            <p id="status"></p>
        `;

        this._csrfToken = this.getAttribute('csrf-token');
        this._saveUrl = this.getAttribute('save-url');
        this._successRedirectUrl = this.getAttribute('success-redirect-url');

        this._saveButton = shadowRoot.querySelector('#save');
        this._saveButton.addEventListener('click', () => this._save());
        this._resetButton = shadowRoot.querySelector('#reset');
        this._resetButton.addEventListener('click', () => this._resetDirtyElements());
        this._status = shadowRoot.querySelector('#status');

        this._elements = this.querySelectorAll('artist-configuration');

        this._dirtyElements = new Set();
        this.addEventListener('dirtyelement', (e) => {
            this._dirtyElements.add(e.detail.dirtyElement);
            this._dirtyElementsUpdated();
        });
        this.addEventListener('cleanelement', (e) => {
            this._dirtyElements.delete(e.detail.cleanElement);
            this._dirtyElementsUpdated();
        });
    }

    _dirtyElementsUpdated() {
        this._saveButton.disabled = this._dirtyElements.size === 0;
        this._resetButton.disabled = this._dirtyElements.size === 0;
    }

    _resetDirtyElements() {
        for (const el of this._dirtyElements.values()) {
            el.reset();
        }

        this._dirtyElements.clear();
        this._dirtyElementsUpdated();
    }

    _save() {
        const payload = {
            artists: {},
        };

        for (const el of this._dirtyElements.values()) {
            payload.artists[el.id] = el.value;
        }

        this._setSavingState();
        fetch(this._saveUrl, {
            method: 'POST',
            headers: {
                'X-CSRF-Token': this._csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((resp) => {
                if (resp.status === 200) {
                    window.location = this._successRedirectUrl;
                } else {
                    this._saveFailed('Error encountered while saving');
                }
            })
            .catch(() => {
                this._saveFailed('Error encountered while saving');
            });
    }

    _setSavingState() {
        this._status.innerHTML = 'Saving...';
        this._saveButton.disabled = true;
        this._resetButton.disabled = true;
        for (const el of this._elements) {
            el.disabled = true;
        }
    }

    _saveFailed(error) {
        this._status.innerHTML = error;
        this._saveButton.disabled = false;
        this._resetButton.disabled = false;
        for (const el of this._elements) {
            el.disabled = false;
        }
    }
}

window.customElements.define('artists-edit-form', ArtistsEditForm);
