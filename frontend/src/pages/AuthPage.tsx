import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import PageFrame from "../components/common/PageFrame";
import { useAuth } from "../auth";
import { useLanguage } from "../i18n";

function normalizePhone(value: string) {
  return value.replace(/\D/g, "").slice(-10);
}

export default function AuthPage({
  mode: _mode,
}: {
  mode: "login" | "register";
}) {
  const {
    login,
    requestCitizenOtp,
    verifyCitizenOtp,
  } = useAuth();

  const { t, language } = useLanguage();

  const navigate = useNavigate();
  const location = useLocation();

  const [portal, setPortal] = useState<
    "citizen" | "admin"
  >("citizen");

  const [citizenStep, setCitizenStep] =
    useState<"details" | "otp">(
      "details",
    );

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [demoOtp, setDemoOtp] =
    useState("");
  const [deliveryMode, setDeliveryMode] =
    useState("demo");
  const [expiresIn, setExpiresIn] =
    useState(0);
  const [retryAfter, setRetryAfter] =
    useState(0);

  const [adminEmail, setAdminEmail] =
    useState("");
  const [adminPassword, setAdminPassword] =
    useState("");

  const [error, setError] =
    useState("");
  const [info, setInfo] =
    useState("");
  const [busy, setBusy] =
    useState(false);

  useEffect(() => {
    if (
      expiresIn <= 0 &&
      retryAfter <= 0
    ) {
      return;
    }

    const timer =
      window.setInterval(() => {
        setExpiresIn((value) =>
          Math.max(0, value - 1),
        );
        setRetryAfter((value) =>
          Math.max(0, value - 1),
        );
      }, 1000);

    return () =>
      window.clearInterval(timer);
  }, [
    expiresIn,
    retryAfter,
  ]);

  const destination = () => {
    const from = (
      location.state as {
        from?: string;
      } | null
    )?.from;

    if (
      from &&
      !from.startsWith("/login") &&
      !from.startsWith("/register")
    ) {
      return from;
    }

    return "/report";
  };

  const requestOtp = async (
    event: FormEvent,
  ) => {
    event.preventDefault();
    setError("");
    setInfo("");

    const normalized =
      normalizePhone(phone);

    if (
      normalized.length !== 10 ||
      !/^[6789]/.test(normalized)
    ) {
      setError(
        t("auth.invalidPhone"),
      );
      return;
    }

    setBusy(true);

    try {
      const response =
        await requestCitizenOtp({
          phone: normalized,
          name:
            name.trim() ||
            undefined,
          email:
            email.trim() ||
            undefined,
          language,
        });

      setPhone(normalized);
      setDemoOtp(
        response.demo_otp ?? "",
      );
      setDeliveryMode(
        response.delivery_mode,
      );
      setInfo(
        response.message ||
          t("auth.codeSent"),
      );
      setExpiresIn(
        response.expires_in_seconds,
      );
      setRetryAfter(
        response.retry_after_seconds,
      );
      setCitizenStep("otp");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("auth.sendError"),
      );
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async (
    event: FormEvent,
  ) => {
    event.preventDefault();
    setError("");
    setInfo("");

    if (
      !/^\d{6}$/.test(
        otp.trim(),
      )
    ) {
      setError(
        t("auth.invalidOtp"),
      );
      return;
    }

    setBusy(true);

    try {
      await verifyCitizenOtp(
        phone,
        otp.trim(),
      );

      navigate(
        destination(),
        { replace: true },
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("auth.verifyError"),
      );
    } finally {
      setBusy(false);
    }
  };

  const adminSubmit = async (
    event: FormEvent,
  ) => {
    event.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);

    try {
      const user =
        await login(
          adminEmail,
          adminPassword,
        );

      navigate(
        user.role === "admin"
          ? "/admin"
          : destination(),
        { replace: true },
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("auth.verifyError"),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageFrame>
      <section className="auth-shell citizen-shell">
        <div className="public-page-heading">
          <div className="section-kicker">
            {t("auth.citizen")}
          </div>
          <h1>{t("auth.pageTitle")}</h1>
          <p>{t("auth.pageCopy")}</p>
        </div>

        <div className="auth-layout">
          <div className="auth-intro">
            <div className="government-panel-title">
              {t("auth.simple")}
            </div>

            <h2>
              {t("auth.easyTitle")}
            </h2>

            <p>
              {t("auth.easyCopy")}
            </p>

            <div className="auth-points">
              <div>
                <span>01</span>
                <div>
                  <strong>
                    {t("auth.point1")}
                  </strong>
                  <p>
                    {t("auth.point1Copy")}
                  </p>
                </div>
              </div>

              <div>
                <span>02</span>
                <div>
                  <strong>
                    {t("auth.point2")}
                  </strong>
                  <p>
                    {t("auth.point2Copy")}
                  </p>
                </div>
              </div>

              <div>
                <span>03</span>
                <div>
                  <strong>
                    {t("auth.point3")}
                  </strong>
                  <p>
                    {t("auth.point3Copy")}
                  </p>
                </div>
              </div>
            </div>

            <div className="auth-language-note">
              {t("auth.languageNote")} · {language.toUpperCase()}
            </div>
          </div>

          <div className="auth-card">
            <div className="portal-tabs">
              <button
                type="button"
                className={
                  portal === "citizen"
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setPortal("citizen");
                  setError("");
                  setInfo("");
                }}
              >
                {t("auth.citizen")}
              </button>

              <button
                type="button"
                className={
                  portal === "admin"
                    ? "active"
                    : ""
                }
                onClick={() => {
                  setPortal("admin");
                  setError("");
                  setInfo("");
                }}
              >
                {t("auth.admin")}
              </button>
            </div>

            {portal === "citizen" ? (
              citizenStep === "details" ? (
                <form
                  onSubmit={requestOtp}
                >
                  <div className="auth-card-heading">
                    <div className="auth-number">
                      01
                    </div>
                    <div>
                      <div className="section-kicker">
                        {t("auth.citizen")}
                      </div>
                      <h2>
                        {t("auth.mobileTitle")}
                      </h2>
                    </div>
                  </div>

                  <p className="auth-note">
                    {t("auth.noPassword")}
                  </p>

                  <label className="field-label">
                    {t("auth.mobile")}
                  </label>

                  <div className="phone-input-row">
                    <span>+91</span>
                    <input
                      className="input-ui"
                      value={phone}
                      onChange={(event) =>
                        setPhone(
                          normalizePhone(
                            event.target.value,
                          ),
                        )
                      }
                      inputMode="numeric"
                      maxLength={10}
                      placeholder={t(
                        "auth.mobilePlaceholder",
                      )}
                      autoFocus
                    />
                  </div>

                  <label className="field-label mt-5">
                    {t("auth.name")} {" "}
                    <span>
                      {t("auth.firstTime")}
                    </span>
                  </label>

                  <input
                    className="input-ui"
                    value={name}
                    onChange={(event) =>
                      setName(
                        event.target.value,
                      )
                    }
                    placeholder={t(
                      "auth.namePlaceholder",
                    )}
                  />

                  <label className="field-label mt-5">
                    {t("auth.email")} {" "}
                    <span>
                      {t("auth.optional")}
                    </span>
                  </label>

                  <input
                    className="input-ui"
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(
                        event.target.value,
                      )
                    }
                    placeholder={t(
                      "auth.emailPlaceholder",
                    )}
                  />

                  {error && (
                    <div className="auth-error">
                      {error}
                    </div>
                  )}

                  {info && (
                    <div className="auth-info">
                      {info}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={busy}
                    className="citizen-primary-btn w-full mt-6"
                  >
                    {busy
                      ? t(
                          "auth.sending",
                        )
                      : t(
                          "auth.sendOtp",
                        )}
                  </button>

                  {deliveryMode ===
                    "demo" && (
                    <div className="demo-note">
                      {t(
                        "auth.demo",
                      )}
                    </div>
                  )}
                </form>
              ) : (
                <form
                  onSubmit={verifyOtp}
                >
                  <div className="auth-card-heading">
                    <div className="auth-number">
                      02
                    </div>
                    <div>
                      <div className="section-kicker">
                        {t("auth.citizen")}
                      </div>
                      <h2>
                        {t("auth.otpTitle")}
                      </h2>
                    </div>
                  </div>

                  <p className="auth-note">
                    +91 {phone} · {t("auth.otpExpires")} {" "}
                    {Math.max(
                      0,
                      Math.ceil(
                        expiresIn / 60,
                      ),
                    )} {" "}
                    {t("auth.minutes")}
                  </p>

                  {info && (
                    <div className="auth-info">
                      {info}
                    </div>
                  )}

                  {demoOtp && (
                    <div className="otp-demo-box">
                      <div>
                        <span>
                          {t("auth.demoCode")}
                        </span>
                        <strong>
                          {demoOtp}
                        </strong>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          setOtp(
                            demoOtp,
                          )
                        }
                      >
                        {t("auth.useCode")}
                      </button>
                    </div>
                  )}

                  <label className="field-label">
                    {t("auth.otp")}
                  </label>

                  <input
                    className="input-ui otp-input"
                    value={otp}
                    onChange={(event) =>
                      setOtp(
                        event.target.value
                          .replace(
                            /\D/g,
                            "",
                          )
                          .slice(0, 6),
                      )
                    }
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    autoFocus
                  />

                  {error && (
                    <div className="auth-error">
                      {error}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={
                      busy ||
                      expiresIn <= 0
                    }
                    className="citizen-primary-btn w-full mt-5"
                  >
                    {busy
                      ? t(
                          "auth.verifying",
                        )
                      : t(
                          "auth.verify",
                        )}
                  </button>

                  <div className="otp-footer-row">
                    <button
                      type="button"
                      className="text-link-button"
                      onClick={() => {
                        setCitizenStep(
                          "details",
                        );
                        setDemoOtp("");
                        setOtp("");
                        setError("");
                        setInfo("");
                      }}
                    >
                      {t("auth.change")}
                    </button>

                    <button
                      type="button"
                      className="text-link-button"
                      disabled={
                        retryAfter > 0 ||
                        busy
                      }
                      onClick={requestOtp}
                    >
                      {retryAfter > 0
                        ? `${t("auth.resend")} ${retryAfter}s`
                        : t("auth.resend")}
                    </button>
                  </div>
                </form>
              )
            ) : (
              <form
                onSubmit={adminSubmit}
              >
                <div className="auth-card-heading">
                  <div className="auth-number">
                    A
                  </div>
                  <div>
                    <div className="section-kicker">
                      {t("auth.admin")}
                    </div>
                    <h2>
                      {t(
                        "auth.adminTitle",
                      )}
                    </h2>
                  </div>
                </div>

                <p className="auth-note">
                  {t("auth.adminCopy")}
                </p>

                <label className="field-label">
                  {t("auth.adminEmail")}
                </label>

                <input
                  className="input-ui"
                  type="email"
                  value={adminEmail}
                  onChange={(event) =>
                    setAdminEmail(
                      event.target.value,
                    )
                  }
                  placeholder="admin@example.com"
                  autoFocus
                />

                <label className="field-label mt-5">
                  {t("auth.password")}
                </label>

                <input
                  className="input-ui"
                  type="password"
                  value={adminPassword}
                  onChange={(event) =>
                    setAdminPassword(
                      event.target.value,
                    )
                  }
                  placeholder={t(
                    "auth.passwordPlaceholder",
                  )}
                />

                {error && (
                  <div className="auth-error">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className="citizen-primary-btn w-full mt-6"
                >
                  {busy
                    ? t(
                        "auth.verifying",
                      )
                    : t(
                        "auth.adminButton",
                      )}
                </button>

                <div className="admin-demo-note">
                  {t("auth.adminNotice")}
                </div>
              </form>
            )}
          </div>
        </div>
      </section>
    </PageFrame>
  );
}
