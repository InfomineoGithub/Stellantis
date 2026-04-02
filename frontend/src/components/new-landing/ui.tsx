import * as React from "react";

export const Button = ({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button
    className={`transition-all duration-300 ${className}`}
    {...props}
  >
    {children}
  </button>
);

export const GoogleIcon = ({ className }: { className?: string }) => (
  <svg className={className} height="18" viewBox="0 0 18 18" width="18">
    <path
      d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84c-.21 1.12-.84 2.07-1.79 2.7l2.85 2.21c1.67-1.53 2.63-3.79 2.63-6.56z"
      fill="#4285F4"
    ></path>
    <path
      d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.85-2.21c-.79.53-1.8.85-3.11.85-2.39 0-4.41-1.61-5.14-3.77H.9v2.32C2.38 15.96 5.45 18 9 18z"
      fill="#34A853"
    ></path>
    <path
      d="M3.86 10.69c-.19-.56-.3-1.15-.3-1.76s.11-1.2.3-1.76V4.85H.9a8.98 8.98 0 0 0 0 8.3l2.96-2.46z"
      fill="#FBBC05"
    ></path>
    <path
      d="M9 3.58c1.32 0 2.5.45 3.44 1.35L15 2.37C13.47.9 11.43 0 9 0 5.45 0 2.38 2.04.9 4.85l2.96 2.46c.73-2.16 2.75-3.77 5.14-3.77z"
      fill="#EA4335"
    ></path>
  </svg>
);
