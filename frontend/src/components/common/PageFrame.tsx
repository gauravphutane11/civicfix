import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth";
import { LanguageSelect, useLanguage } from "../../i18n";

function Icon({
  name,
}: {
  name: "report" | "list" | "home" | "user" | "logout";
}) {
  const paths = {
    report: (
      <>
        <path d="M12 5v14M5 12h14" />
        <rect x="4" y="4" width="16" height="16" rx="4" />
      </>
    ),
    list: (
      <>
        <path d="M6 7h12M6 12h12M6 17h8" />
      </>
    ),
    home: (
      <>
        <path d="m4 11 8-7 8 7" />
        <path d="M6 10v9h12v-9" />
        <path d="M10 19v-5h4v5" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="3" />
        <path d="M5 20c.8-3.2 3.1-5 7-5s6.2 1.8 7 5" />
      </>
    ),
    logout: (
      <>
        <path d="M10 6H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4" />
        <path d="M13 8l4 4-4 4M17 12H8" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-4 h-4"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export default function PageFrame({
  children,
}: {
  children: ReactNode;
}) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();

  const citizen = user?.role === "citizen";
  const is = (path: string) =>
    location.pathname === path ||
    location.pathname.startsWith(`${path}/`);

  const citizenPath = citizen ? "/report" : "/login";
  const complaintsPath = citizen ? "/complaints" : "/login";

  return (
    <div className="citizen-app min-h-screen">
      <div className="citizen-utility">
        <div className="citizen-shell utility-inner">
          <div className="utility-message">
            {t("utility.message")}
          </div>

          <div className="utility-links">
            <Link to="/">{t("nav.home")}</Link>
            <span aria-hidden="true">|</span>
            <a href="/#how-it-works" onClick={(event) => {
              if (location.pathname === "/") return;
              event.preventDefault();
              navigate("/#how-it-works");
            }}>{t("nav.help")}</a>
          </div>
        </div>
      </div>

      <header className="citizen-header">
        <div className="citizen-shell citizen-header-inner">
          <Link
            to="/"
            className="citizen-brand"
          >
            <div className="citizen-brand-mark">CF</div>
            <div>
              <div className="citizen-brand-name">
                CivicFix
              </div>
              <div className="citizen-brand-sub">
                {t("utility.message")}
              </div>
            </div>
          </Link>

          <nav className="citizen-nav hidden lg:flex">
            <Link
              className={is("/") ? "active" : ""}
              to="/"
            >
              <Icon name="home" />
              {t("nav.home")}
            </Link>

            <Link
              className={is("/report") ? "active" : ""}
              to={citizenPath}
            >
              <Icon name="report" />
              {t("nav.report")}
            </Link>

            <Link
              className={is("/track") ? "active" : ""}
              to={citizenPath}
            >
              <Icon name="list" />
              {t("nav.track")}
            </Link>

            <Link
              className={is("/complaints") ? "active" : ""}
              to={complaintsPath}
            >
              {t("nav.complaints")}
            </Link>
          </nav>

          <div className="citizen-actions">
            <LanguageSelect />

            {user ? (
              <>
                <div className="citizen-user-pill hidden sm:flex">
                  <span className="citizen-user-avatar">
                    {user.name
                      .slice(0, 1)
                      .toUpperCase()}
                  </span>
                  <span className="max-w-[130px] truncate">
                    {user.name}
                  </span>
                </div>

                <button
                  type="button"
                  className="citizen-outline-btn compact"
                  onClick={() => {
                    logout();
                    navigate("/", {
                      replace: true,
                    });
                  }}
                >
                  <Icon name="logout" />
                  <span className="hidden sm:inline">
                    {t("nav.logout")}
                  </span>
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="citizen-login-btn"
              >
                <Icon name="user" />
                {t("nav.login")}
              </Link>
            )}
          </div>
        </div>
      </header>

      <div className="citizen-service-nav">
        <div className="citizen-shell citizen-service-nav-inner">
          <Link to={citizenPath}>{t("nav.report")}</Link>
          <Link to={citizenPath}>{t("nav.track")}</Link>
          <Link to={complaintsPath}>{t("nav.complaints")}</Link>
          <a href="#help">{t("nav.help")}</a>
        </div>
      </div>

      <main>{children}</main>

      <footer
        className="citizen-footer"
        id="help"
      >
        <div className="citizen-shell footer-grid">
          <div>
            <div className="citizen-brand footer-brand">
              <div className="citizen-brand-mark">CF</div>
              <div>
                <div className="citizen-brand-name">
                  CivicFix
                </div>
                <div className="citizen-brand-sub">
                  {t("utility.message")}
                </div>
              </div>
            </div>

            <p className="footer-copy">
              {t("footer.disclaimer")}
            </p>
          </div>

          <div>
            <div className="footer-heading">
              {t("footer.services")}
            </div>
            <Link to={citizenPath}>
              {t("nav.report")}
            </Link>
            <Link to={complaintsPath}>
              {t("nav.complaints")}
            </Link>
            <Link to={citizenPath}>
              {t("nav.track")}
            </Link>
          </div>

          <div>
            <div className="footer-heading">
              {t("nav.language")}
            </div>
            <LanguageSelect />
          </div>
        </div>
      </footer>
    </div>
  );
}
