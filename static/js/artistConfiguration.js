class ArtistConfiguration extends HTMLElement {
    constructor() {
        super();

        this._defaultChecked = this.hasAttribute('saved');

        const shadowRoot = this.attachShadow({ mode: 'open' });
        shadowRoot.innerHTML = `
            <style>
                label.changed {
                    font-weight: bold;
                }
            </style>
            <label>
                <input type="checkbox"${this._defaultChecked ? ' checked' : ''}>
                ${this.getAttribute('name')}
            </label>
        `;

        this._label = shadowRoot.querySelector('label');
        this._checkbox = shadowRoot.querySelector('input');
        this._checkbox.addEventListener('change', (e) => {
            if (e.target.checked !== this._defaultChecked) {
                this._label.classList.toggle('changed', true);
                this.dispatchEvent(
                    new CustomEvent('dirtyelement', {
                        bubbles: true,
                        detail: {
                            dirtyElement: this,
                        },
                    })
                );
            } else {
                this._label.classList.toggle('changed', false);
                this.dispatchEvent(
                    new CustomEvent('cleanelement', {
                        bubbles: true,
                        detail: {
                            cleanElement: this,
                        },
                    })
                );
            }
        });
    }

    _updateDisabledState() {
        this._checkbox.disabled = this.disabled;
    }

    static get observedAttributes() {
        return ['disabled'];
    }

    attributeChangedCallback(name) {
        if (name === 'disabled') {
            this._updateDisabledState();
        }
    }

    reset() {
        this._checkbox.checked = this._defaultChecked;
        this._label.classList.toggle('changed', false);
    }

    get id() {
        return this.getAttribute('id');
    }

    get value() {
        return this._checkbox.checked;
    }

    get disabled() {
        return this.hasAttribute('disabled');
    }

    set disabled(val) {
        if (val) {
            this.setAttribute('disabled', '');
        } else {
            this.removeAttribute('disabled');
        }

        this._updateDisabledState();
    }
}

window.customElements.define('artist-configuration', ArtistConfiguration);
