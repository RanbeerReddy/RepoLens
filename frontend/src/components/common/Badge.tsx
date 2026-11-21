import React from 'react';
import { getEntityBgColor } from '@/utils/format';

interface BadgeProps {
  type: string;
  label?: string;
}

const Badge: React.FC<BadgeProps> = ({ type, label }) => {
  const colorClasses = getEntityBgColor(type);

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${colorClasses}`}
    >
      {label || type}
    </span>
  );
};

export default Badge;
