(function() {
    'use strict';
    
    // Remove any existing footer first
    const existing = document.querySelector('.ayur-footer');
    if (existing) existing.remove();
    
    const footerHTML = `
        <footer class="ayur-footer" style="
            background: #0B120E;
            border-top: 1px solid rgba(45, 139, 106, 0.08);
            padding: 20px 32px 16px;
            margin-top: 40px;
            font-family: 'Geist', sans-serif;
        ">
            <div style="
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            ">
                <!-- Left: Copyright -->
                <span style="
                    color: #4a6a5a;
                    font-size: 12px;
                    letter-spacing: 0.3px;
                ">© 2026 AYUR-INTEL. All rights reserved.</span>
                
                <!-- Right: Made with -->
                <span style="
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    color: #4a6a5a;
                    font-size: 12px;
                ">
                    Made with 
                    <span style="color: #ff6b6b; font-size: 13px;">❤</span>
                    by 
                    <span style="color: #7dba9a; font-weight: 500;">AYUR-INTEL</span>
                </span>
            </div>
        </footer>
    `;
    
    function injectFooter() {
        const prev = document.querySelector('.ayur-footer');
        if (prev) prev.remove();
        const app = document.querySelector('.app');
        if (app) {
            app.insertAdjacentHTML('afterend', footerHTML);
        } else if (document.body) {
            document.body.insertAdjacentHTML('beforeend', footerHTML);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectFooter);
    } else {
        injectFooter();
    }
})();
