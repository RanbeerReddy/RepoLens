export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

export function getEntityColor(entityType: string): string {
  switch (entityType.toLowerCase()) {
    case 'function':
      return 'blue';
    case 'class':
      return 'purple';
    case 'file':
      return 'green';
    case 'module':
      return 'yellow';
    default:
      return 'gray';
  }
}

export function getEntityIcon(entityType: string): string {
  switch (entityType.toLowerCase()) {
    case 'function':
      return 'FunctionSquare';
    case 'class':
      return 'Box';
    case 'file':
      return 'FileCode';
    case 'module':
      return 'Package';
    default:
      return 'Code';
  }
}

export function getEntityBgColor(entityType: string): string {
  switch (entityType.toLowerCase()) {
    case 'function':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'class':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'file':
      return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'module':
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}
