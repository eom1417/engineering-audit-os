"""How an endpoint is guarded, read from its handler's text (M6.4): who is signed in (authentication), whether the row is
theirs or their role allows it (authorisation), and whether its input is checked (validation). Each answer names what
was read; a guard EAOS cannot read (a middleware or wrapper it does not know) is a question, never a finding."""
import re

# Comments are not code: a guard written in a comment guards nothing (a handler whose body is commented out writes nothing).
COMMENTS = {'python': re.compile(r'#[^\n]*'), '': re.compile(r'/\*.*?\*/|(?<![:\'"\\])//[^\n]*', re.S)}

AUTHENTICATION = re.compile(
    r'\b(signedIn|isAuthenticated|is_authenticated|requireAuth|require_auth|ensureAuth\w*|authenticate\w*|verifyToken|'
    r'verify_token|jwt\.verify|jwtVerify|getServerSession|getSession|getToken|currentUser|current_user|getUser|get_user|'
    r'getAuth|requireUser|require_user|login_required|LoginRequired\w*|jwt_required|passport\.authenticate|withAuth|'
    r'withApiAuth\w*|isLoggedIn|is_logged_in|checkAuth|check_auth|protect\w*|auth\.protect|clerkClient|validateRequest|'
    r'validateSession|lucia\.\w+|IsAuthenticated|permission_classes|get_current_user\w*|Security\(|HTTPBearer|OAuth2PasswordBearer)\b'
    r'|\b(?:req|request)\.(?:user|auth|session\.user(?:Id)?)\b|\bawait\s+auth\(\)|\bsession\?*\.user\b|\buser\s*=\s*await\s+auth\(')
AUTHORISATION = re.compile(
    r'\b(owner\w*|user_?id|userId|author_?id|authorId|created_?by|createdBy|profile_?id|account_?id|tenant_?id|org_?id|'
    r'role|roles|isAdmin|is_admin|is_staff|is_superuser|permission\w*|authori[sz]e\w*|can\(|has_perm\w*|has_role|hasRole|'
    r'IsOwner\w*|PermissionRequired\w*|UserPassesTest\w*)\b|auth\.uid\(\)|[!=]==?\s*(?:user|req\.user\.id|session\.user\.id)\b'
    r'|\bfilter\(\s*(?:owner|user|author)\s*=|\.eq\(\s*[\'"]\w*(?:user|owner|author)\w*[\'"]')
VALIDATION = re.compile(
    r'\.(?:parse|safeParse|parseAsync|safeParseAsync|validate\w*|is_valid)\s*\(|\b(?:z|zod|Joi|joi|yup|v|t)\.object\s*\(|'
    r'\b(?:celebrate|checkSchema|validationResult|ajv|Ajv|plainToInstance|class-validator|validate)\b|'
    r'\bBaseModel\b|\bSchema\(\)|\bserializer\w*\.is_valid|\bform\.is_valid|typeof\s+\w+(?:\.\w+)*\s*!?==|'
    r'Number\.is(?:Integer|Finite)|isNaN\(|OpenApiValidator|\bpydantic\b|: \w+Model\b|@validate')
# A webhook proves who calls it by a signature, not a session.
SIGNATURE = re.compile(r'constructEvent|verifySignature|verify_signature|x-hub-signature|x-signature|svix|webhook_secret|'
                       r'WEBHOOK_SECRET|hmac|timingSafeEqual|compare_digest|x-api-key|X-API-Key|api_key\s*!?==|apiKey\s*!?==', re.I)
# Endpoints that are public by what they are for: signing in or up, a password reset, a health check, the sign-in flow's own.
# A webhook or a callback is not among them: it proves its caller by a signature (SIGNATURE), or it is open.
PUBLIC = re.compile(r'(^|[/_:-])(login|log-in|signin|sign-in|sign_in|signup|sign-up|sign_up|register|logout|sign-?out|auth|oauth|'
                    r'token|refresh|password|forgot|health|healthz|ping|ready|live|status|version|metrics|csrf|session)([/_.-]|$)', re.I)
# A request's own token forwarded to Supabase, or its cookies: the database then knows the person, and its row-level
# security decides what they reach.
USER_CLIENT = re.compile(r'createServerClient|createRouteHandlerClient|createServerActionClient|createServerComponentClient|'
                         r'headers:\s*\{\s*Authorization:\s*(?:req|request)\.headers|Authorization:\s*authHeader|'
                         r'global:\s*\{\s*headers:\s*\{\s*Authorization', re.S)
SERVICE_CLIENT = re.compile(r'SERVICE_ROLE|service_role|SUPABASE_SECRET|sb_secret_')
MIDDLEWARE_ARGS = re.compile(r'''\.(?:get|post|put|patch|delete|all)\(\s*['"`][^'"`]*['"`]\s*,\s*(?P<args>[^)]*?)\s*,\s*(?:async\s*)?(?:\(|function|\w+\s*\)|[A-Za-z_$][\w$.]*\s*\)\s*;?\s*$)''')


def code(text, language):
    """The text without its comments."""
    return COMMENTS['python' if language == 'python' else ''].sub('', text)


def read(text):
    """{'authentication', 'authorisation', 'validation', 'signature', 'user_client', 'service_client'}: the first words that
    say each, or None."""
    found = {}
    for name, pattern in (('authentication', AUTHENTICATION), ('authorisation', AUTHORISATION), ('validation', VALIDATION),
                          ('signature', SIGNATURE), ('user_client', USER_CLIENT), ('service_client', SERVICE_CLIENT)):
        match = pattern.search(text)
        found[name] = match.group(0).strip()[:60] if match else None
    return found


def public(route):
    return bool(PUBLIC.search(str(route or '')))


def unknown_middleware(route_line):
    """The names an Express-like route passes before its handler that say nothing EAOS reads: a guard it cannot judge."""
    match = MIDDLEWARE_ARGS.search(route_line)
    if not match: return []
    names = [part.strip() for part in match.group('args').split(',') if re.fullmatch(r'[A-Za-z_$][\w$.]*(\(\))?', part.strip())]
    return [name for name in names if not (AUTHENTICATION.search(name) or VALIDATION.search(name + '('))]
