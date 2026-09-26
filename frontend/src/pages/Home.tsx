import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageFrame from "../components/common/PageFrame";
import { useAuth } from "../auth";
import { useLanguage } from "../i18n";

const ISSUE_MEDIA = [
  {
    category: "pothole",
    image: "/issues/pothole.svg",
    title: "Potholes & road damage",
    copy: "A pothole, broken road or unsafe road surface.",
  },
  {
    category: "drainage",
    image: "/issues/drainage.svg",
    title: "Blocked drains & waterlogging",
    copy: "Water collecting because a drain is blocked or overflowing.",
  },
  {
    category: "garbage",
    image: "/issues/garbage.svg",
    title: "Garbage & waste",
    copy: "Overflowing bins, loose waste or dirty public areas.",
  },
  {
    category: "streetlight",
    image: "/issues/streetlight.svg",
    title: "Broken streetlights",
    copy: "A streetlight that is out, damaged or unsafe at night.",
  },
  {
    category: "sidewalk",
    image: "/issues/sidewalk.svg",
    title: "Broken footpaths & sidewalks",
    copy: "Broken tiles, uneven paths or blocked walking space.",
  },
  {
    category: "water_supply",
    image: "/issues/water.svg",
    title: "Water supply problems",
    copy: "A leak, low pressure, dirty water or no water.",
  },
];

export default function Home() {
  const { user } = useAuth();
  const { t, categoryLabel } = useLanguage();
  const citizen = user?.role === "citizen";
  const admin = user?.role === "admin";
  const [activeSlide, setActiveSlide] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveSlide((value) =>
        (value + 1) % ISSUE_MEDIA.length,
      );
    }, 5000);

    return () => window.clearInterval(timer);
  }, []);

  const current = ISSUE_MEDIA[activeSlide];
  const actionPath = citizen ? "/report" : "/login";

  return (
    <PageFrame>
      <section className="public-hero">
        <div className="citizen-shell public-hero-inner">
          <div className="public-hero-copy">
            <div className="government-kicker">
              {t("home.kicker")}
            </div>

            <h1>{t("home.title")}</h1>

            <p>{t("home.copy")}</p>

            <div className="public-actions">
              {admin ? (
                <Link
                  to="/admin"
                  className="public-button public-button-saffron"
                >
                  Open admin console
                </Link>
              ) : (
                <>
                  <Link
                    to={actionPath}
                    className="public-button public-button-saffron"
                  >
                    {t("home.report")}
                  </Link>

                  <Link
                    to={actionPath}
                    className="public-button public-button-outline"
                  >
                    {t("home.track")}
                  </Link>
                </>
              )}
            </div>

            <div className="public-trust">
              <span>1. Describe the problem</span>
              <span>2. Add a photo</span>
              <span>3. Share the location</span>
              <span>4. Track the case</span>
            </div>
          </div>

          <div className="issue-feature">
            <div className="issue-feature-image">
              <img
                src={current.image}
                alt={current.title}
                loading="eager"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />

              <div className="issue-feature-overlay" />

              <div className="issue-feature-label">
                <span>{t("home.example")}</span>
                <strong>{categoryLabel(current.category)}</strong>
              </div>
            </div>

            <div className="issue-feature-body">
              <div className="issue-feature-count">
                {String(activeSlide + 1).padStart(2, "0")} / {String(ISSUE_MEDIA.length).padStart(2, "0")}
              </div>

              <h2>{categoryLabel(current.category)}</h2>
              <p>{t("home.issueCopy")}</p>

              <Link
                to={actionPath}
                className="issue-feature-link"
              >
                {t("home.report")} →
              </Link>
            </div>

            <div className="issue-dots">
              {ISSUE_MEDIA.map((item, index) => (
                <button
                  type="button"
                  key={item.category}
                  className={index === activeSlide ? "active" : ""}
                  aria-label={`Show ${item.title}`}
                  onClick={() => setActiveSlide(index)}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="public-maroon-strip">
        <div className="citizen-shell">
          <strong>{t("home.issues")}</strong>
          <span>{t("home.stripCopy")}</span>
        </div>
      </section>

      <section className="citizen-section">
        <div className="citizen-shell">
          <div className="section-heading-row">
            <div>
              <div className="section-kicker">{t("home.services")}</div>
              <h2>{t("home.issues")}</h2>
            </div>

            <Link
              to={actionPath}
              className="text-link"
            >
              {t("home.report")} →
            </Link>
          </div>

          <div className="public-issue-grid">
            {ISSUE_MEDIA.map((item, index) => (
              <Link
                key={item.category}
                to={actionPath}
                className="public-issue-card"
              >
                <div className="public-issue-image">
                  <img
                    src={item.image}
                    alt={item.title}
                    loading="lazy"
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                  />
                </div>

                <div className="public-issue-content">
                  <div className="public-issue-number">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <h3>{categoryLabel(item.category)}</h3>
                  <p>{t("home.issueCopy")}</p>
                </div>
              </Link>
            ))}
          </div>

          <p className="media-credit">
            {t("home.mediaNote")}
          </p>
        </div>
      </section>

      <section
        id="how-it-works"
        className="citizen-section civic-guide-section"
      >
        <div className="citizen-shell">
          <div className="section-heading-row">
            <div>
              <div className="section-kicker">{t("home.how")}</div>
              <h2>{t("home.how")}</h2>
            </div>

            <p>
              {t("home.guideCopy")}
            </p>
          </div>

          <div className="public-step-grid">
            <article>
              <span>01</span>
              <h3>{t("home.step1")}</h3>
              <p>{t("home.step1Copy")}</p>
            </article>

            <article>
              <span>02</span>
              <h3>{t("home.step2")}</h3>
              <p>{t("home.step2Copy")}</p>
            </article>

            <article>
              <span>03</span>
              <h3>{t("home.step3")}</h3>
              <p>{t("home.step3Copy")}</p>
            </article>
          </div>
        </div>
      </section>

      <section className="citizen-section public-footer-cta">
        <div className="citizen-shell public-footer-cta-inner">
          <div>
            <div className="section-kicker">{t("home.citizenAccess")}</div>
            <h2>{t("home.footerTitle")}</h2>
            <p>{t("home.footerCopy")}</p>
          </div>

          <Link
            to={actionPath}
            className="public-button public-button-saffron"
          >
            {t("home.report")} →
          </Link>
        </div>
      </section>
    </PageFrame>
  );
}
