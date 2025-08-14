import createMiddleware from 'next-intl/middleware';

export default createMiddleware({
  locales: ['en', 'vi', 'kr', 'ja'],
  defaultLocale: 'en'
});

export const config = {
  matcher: ['/((?!_next|.*\\.\w+$).*)']
};


