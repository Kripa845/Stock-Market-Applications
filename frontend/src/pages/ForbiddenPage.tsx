import { ShieldOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ForbiddenPageProps {
  /** Optional permission name shown in the message. */
  requiredPermission?: string;
  /** Custom heading. */
  title?: string;
  /** Custom body text. */
  message?: string;
}

export default function ForbiddenPage({
  requiredPermission,
  title = 'Access Restricted',
  message,
}: ForbiddenPageProps) {
  const navigate = useNavigate();

  const body =
    message ??
    (requiredPermission
      ? `You do not have the "${requiredPermission}" permission required to access this page.`
      : 'You do not have permission to access this page.');

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-down/10">
        <ShieldOff size={40} className="text-down" />
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold tracking-widest text-down uppercase">
          403 Forbidden
        </p>
        <h1 className="text-2xl font-bold text-text-primary">{title}</h1>
        <p className="max-w-md text-sm text-text-secondary leading-relaxed">{body}</p>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => navigate(-1)}
          className="btn-ghost"
        >
          Go Back
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          className="btn-primary"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
}
